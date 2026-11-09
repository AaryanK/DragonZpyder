"""PostgreSQL-backed scheduled goal reconciler for DragonZpyder's Hatchet worker.

Every due occurrence is uniquely recorded before execution. Recurring ticks
replay pending work and reclaim expired leases after a worker crash. Only a
dedicated, operator-owned synthetic principal may execute in this phase.
User goals are recorded as awaiting_authorization; NO personal/workspace tool
or paid model can be invoked from a scheduled wakeup.

Hatchet supplies the durable minute tick and worker assignment. This ledger
handles DB atomicity, replay, leases and cancellation across worker restarts.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from .goal_store import _principal
from .goal_reconciler_schema import RUN_SCHEMA
from .workflows.spec import next_schedule_time

_PROBE_IDENTITY = _principal(
    source_app="internal_canary", kind="personal",
    user_id="internal-staging-probe", workspace_id=None,
)
_MAX_PER_TICK = 20
_LEASE = timedelta(seconds=90)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _canonical_time(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("Scheduler clock must be timezone-aware")
    return value.astimezone(timezone.utc)


class GoalReconciler:
    def __init__(self, pool):
        self._pool = pool

    async def enqueue_due(self, *, now: datetime | None = None, limit: int = _MAX_PER_TICK) -> dict:
        clock = _canonical_time(now or utc_now())
        if not 1 <= limit <= _MAX_PER_TICK:
            raise ValueError("Invalid reconciliation batch")
        result = {"pending": 0, "awaiting_authorization": 0}
        async with self._pool.acquire() as con:
            async with con.transaction():
                due = await con.fetch(
                    """SELECT goal_id, source_app, principal_hash, schedule_json, next_run_at
                       FROM dragonzpyder_goals
                       WHERE status='registered' AND next_run_at <= $1
                       ORDER BY next_run_at, goal_id
                       LIMIT $2 FOR UPDATE SKIP LOCKED""",
                    clock, limit,
                )
                for goal in due:
                    due_at = goal["next_run_at"]
                    schedule = goal["schedule_json"]
                    if isinstance(schedule, str):
                        try:
                            schedule = json.loads(schedule)
                        except (ValueError, TypeError) as exc:
                            raise RuntimeError("Stored schedule malformed") from exc
                    if not isinstance(schedule, dict):
                        raise RuntimeError("Invalid stored schedule; no dispatch")
                    # No user-facing request can register the internal synthetic
                    # principal. Operly goal APIs hardcode source_app=operly.
                    synthetic = (goal["source_app"] == "internal_canary" and
                                 goal["principal_hash"] == _PROBE_IDENTITY)
                    state = "pending" if synthetic else "awaiting_authorization"
                    created = await con.fetchval(
                        """INSERT INTO dragonzpyder_goal_runs
                           (run_id, goal_id, scheduled_for, status)
                           VALUES($1,$2,$3,$4)
                           ON CONFLICT(goal_id, scheduled_for) DO NOTHING
                           RETURNING run_id""",
                        uuid4(), goal["goal_id"], due_at, state,
                    )
                    next_at = next_schedule_time(
                        schedule, after=due_at.astimezone(timezone.utc).replace(tzinfo=None)
                    )
                    # Unapproved user goals are paused after ONE recorded
                    # occurrence. Otherwise a minutely cron could grow an
                    # unbounded backlog of unauthorized user goal records.
                    await con.execute(
                        """UPDATE dragonzpyder_goals
                           SET next_run_at=$2,updated_at=$3,status=$4
                           WHERE goal_id=$1 AND status='registered'""",
                        goal["goal_id"],
                        (next_at.replace(tzinfo=timezone.utc)
                         if next_at and synthetic else None),
                        clock,
                        "registered" if synthetic else "awaiting_authorization",
                    )
                    if created is not None:
                        result[state] += 1
        return result

    async def claim_probe(self, *, now: datetime | None = None) -> dict | None:
        clock = _canonical_time(now or utc_now())
        token = uuid4()
        async with self._pool.acquire() as con:
            async with con.transaction():
                # Exhausted claims cannot be replayed by a later Hatchet tick.
                await con.execute(
                    """UPDATE dragonzpyder_goal_runs r
                       SET status='failed', error_code='attempt_limit',
                           claim_token=NULL, lease_until=NULL, updated_at=$1
                       FROM dragonzpyder_goals g
                       WHERE r.goal_id=g.goal_id AND r.status='running'
                         AND r.lease_until <= $1 AND r.attempts>=3
                         AND g.source_app='internal_canary' AND g.principal_hash=$2""",
                    clock, _PROBE_IDENTITY,
                )
                row = await con.fetchrow(
                    """WITH candidate AS (
                           SELECT r.run_id
                           FROM dragonzpyder_goal_runs r
                           JOIN dragonzpyder_goals g ON g.goal_id=r.goal_id
                           WHERE g.status='registered'
                             AND g.source_app='internal_canary'
                             AND g.principal_hash=$2
                             AND (
                               r.status='pending'
                               OR (r.status='running' AND r.lease_until <= $1)
                             )
                             AND r.attempts < 3
                           ORDER BY r.scheduled_for, r.run_id
                           LIMIT 1 FOR UPDATE OF r SKIP LOCKED
                       )
                       UPDATE dragonzpyder_goal_runs r
                       SET status='running',attempts=r.attempts+1,
                           claim_token=$3,lease_until=$4,updated_at=$1
                       FROM candidate WHERE r.run_id=candidate.run_id
                       RETURNING r.run_id,r.goal_id,r.scheduled_for,
                                 r.attempts,r.claim_token""",
                    clock, _PROBE_IDENTITY, token, clock + _LEASE,
                )
        return dict(row) if row else None

    async def complete_probe(self, claim: dict, *, now: datetime | None = None) -> dict:
        clock = _canonical_time(now or utc_now())
        # Evidence is a deterministic DB-only computation, not a claimed
        # completed user goal. No model, network, shell, or external side effect.
        receipt = "|".join(
            ("dragonzpyder-synthetic-probe-v1", str(claim["goal_id"]),
             claim["scheduled_for"].astimezone(timezone.utc).isoformat())
        )
        digest = hashlib.sha256(receipt.encode()).hexdigest()
        async with self._pool.acquire() as con:
            row = await con.fetchrow(
                """UPDATE dragonzpyder_goal_runs r
                   SET status='completed', evidence_sha256=$3,
                       claim_token=NULL,lease_until=NULL, updated_at=$4
                   WHERE r.run_id=$1 AND r.claim_token=$2 AND r.status='running'
                     AND r.lease_until > $4
                     AND EXISTS (
                       SELECT 1 FROM dragonzpyder_goals g
                       WHERE g.goal_id=r.goal_id AND g.status='registered'
                         AND g.source_app='internal_canary'
                         AND g.principal_hash=$5
                     )
                   RETURNING r.run_id,r.attempts,r.evidence_sha256""",
                claim["run_id"], claim["claim_token"], digest, clock, _PROBE_IDENTITY,
            )
        if row is None:
            return {"status": "not_committed", "reason": "claim_expired_or_cancelled"}
        return {"status": "completed", "run_id": str(row["run_id"]),
                "attempts": row["attempts"],
                "evidence_sha256": row["evidence_sha256"],
                "objective_verified": False, "synthetic_only": True}

    async def tick(self, *, now: datetime | None = None) -> dict:
        clock = _canonical_time(now or utc_now())
        queued = await self.enqueue_due(now=clock)
        results = []
        for _ in range(5):
            claim = await self.claim_probe(now=clock)
            if claim is None:
                break
            results.append(await self.complete_probe(claim, now=clock))
        return {"scheduled": queued, "probes": results,
                "personal_tool_calls": 0, "model_calls": 0}
