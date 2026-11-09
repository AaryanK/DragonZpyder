"""Durable DragonZpyder goal registry, independent of Operly business models.

A stored goal is NOT a running workflow. Hatchet will own wakeups after an
authenticated renewal interface is available. We never persist an Operly
four-minute lease, provider credential, or unencrypted goal text.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from uuid import UUID, uuid4

from cryptography.fernet import Fernet
from .workflows.spec import validate_schedule, next_schedule_time

SCHEMA = """
CREATE TABLE IF NOT EXISTS dragonzpyder_goals (
    goal_id uuid PRIMARY KEY,
    source_app text NOT NULL,
    principal_hash char(64) NOT NULL,
    request_id uuid NOT NULL,
    payload_sha256 char(64) NOT NULL,
    goal_ciphertext bytea NOT NULL,
    schedule_json jsonb,
    next_run_at timestamptz,
    status text NOT NULL DEFAULT 'registered'
      CHECK (status IN ('registered','awaiting_authorization',
                        'paused','cancelled','completed')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(source_app, principal_hash, request_id)
);
CREATE INDEX IF NOT EXISTS idx_dz_goals_due
 ON dragonzpyder_goals (next_run_at)
 WHERE status = 'registered';
"""


# Kept with goal DDL so fresh-database tests initialize the full ledger.
from .goal_reconciler_schema import RUN_SCHEMA
SCHEMA += "\n" + RUN_SCHEMA
from .event_schema import EVENT_SCHEMA
SCHEMA += "\n" + EVENT_SCHEMA


class GoalConflict(RuntimeError):
    pass


def _id(value: str) -> UUID:
    try:
        uid = UUID(value)
        if str(uid) != value:
            raise ValueError()
        return uid
    except (TypeError, AttributeError, ValueError) as exc:
        raise ValueError("A canonical UUID is required") from exc


def _principal(*, source_app: str, kind: str, user_id: str,
               workspace_id: str | None) -> str:
    if source_app not in ("operly", "dragonzpyder", "internal_canary"):
        raise ValueError("Unrecognized authenticated source")
    if kind not in ("personal", "workspace") or not isinstance(user_id, str) or not 1 <= len(user_id) <= 120:
        raise ValueError("Invalid principal scope")
    if kind == "workspace" and (not isinstance(workspace_id, str) or not 1 <= len(workspace_id) <= 120):
        raise ValueError("Workspace identity required")
    if kind == "personal" and workspace_id is not None:
        raise ValueError("Personal requests cannot inherit workspace authority")
    # Serialize distinct fields instead of joining on an attacker-supplied
    # separator: a user ID may legally contain delimiter-like characters.
    canonical = json.dumps(
        ["dz-goal-v2", source_app, kind, user_id, workspace_id],
        separators=(",", ":"), ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _serialize(row) -> dict:
    if row is None:
        raise LookupError("Goal is unavailable")
    return {
        "goal_id": str(row["goal_id"]), "source_app": row["source_app"],
        "status": row["status"], "next_run_at": (
            row["next_run_at"].isoformat() if row["next_run_at"] else None
        ), "schedule": (json.loads(row["schedule_json"]) if isinstance(row["schedule_json"], str)
                     else row["schedule_json"]),
        "job_registered": False, "execution_started": False,
        "requires_fresh_authorization": True,
    }


class DurableGoalStore:
    """Encrypted, idempotent goal storage for trusted API callers only."""

    def __init__(self, pool, *, encryption_key: str):
        if not isinstance(encryption_key, str):
            raise RuntimeError("Goal encryption key is missing")
        try:
            self._cipher = Fernet(encryption_key.encode())
        except (ValueError, TypeError) as exc:
            raise RuntimeError("A valid Fernet goal-encryption key is required") from exc
        self._pool = pool

    async def register(
        self, *, source_app: str, kind: str, user_id: str,
        workspace_id: str | None, request_id: str, goal: str,
        schedule: dict | None,
    ) -> dict:
        principal = _principal(source_app=source_app, kind=kind, user_id=user_id,
                               workspace_id=workspace_id)
        request = _id(request_id)
        if not isinstance(goal, str) or not 1 <= len(goal.strip()) <= 5000:
            raise ValueError("Invalid goal text")
        normalized = validate_schedule(schedule)
        if normalized is not None:
            next_run = next_schedule_time(
                normalized, after=datetime.now(timezone.utc).replace(tzinfo=None)
            )
        else:
            next_run = None
        if next_run is not None:
            next_run = next_run.replace(tzinfo=timezone.utc)
        manifest = json.dumps({"goal": goal, "schedule": normalized}, sort_keys=True,
                              ensure_ascii=True, separators=(",", ":"))
        fingerprint = hashlib.sha256(manifest.encode()).hexdigest()
        ciphertext = self._cipher.encrypt(goal.encode("utf-8"))
        async with self._pool.acquire() as con:
            async with con.transaction():
                row = await con.fetchrow(
                    """INSERT INTO dragonzpyder_goals
                       (goal_id,source_app,principal_hash,request_id,payload_sha256,
                        goal_ciphertext,schedule_json,next_run_at)
                       VALUES($1,$2,$3,$4,$5,$6,$7::jsonb,$8)
                       ON CONFLICT(source_app,principal_hash,request_id) DO NOTHING
                       RETURNING *""",
                    uuid4(), source_app, principal, request, fingerprint,
                    ciphertext, json.dumps(normalized), next_run,
                )
                if row is None:
                    row = await con.fetchrow(
                        """SELECT * FROM dragonzpyder_goals
                           WHERE source_app=$1 AND principal_hash=$2 AND request_id=$3
                           FOR UPDATE""", source_app, principal, request,
                    )
                if row is None or row["payload_sha256"] != fingerprint:
                    raise GoalConflict("Goal registration request cannot be reused with new content")
                return _serialize(row)

    async def get(self, *, source_app: str, kind: str, user_id: str,
                  workspace_id: str | None, goal_id: str) -> dict:
        principal = _principal(source_app=source_app, kind=kind, user_id=user_id,
                               workspace_id=workspace_id)
        async with self._pool.acquire() as con:
            row = await con.fetchrow(
                """SELECT * FROM dragonzpyder_goals
                   WHERE goal_id=$1 AND source_app=$2 AND principal_hash=$3""",
                _id(goal_id), source_app, principal,
            )
        return _serialize(row)

    async def cancel(self, *, source_app: str, kind: str, user_id: str,
                     workspace_id: str | None, goal_id: str) -> dict:
        principal = _principal(source_app=source_app, kind=kind, user_id=user_id,
                               workspace_id=workspace_id)
        async with self._pool.acquire() as con:
            async with con.transaction():
                row = await con.fetchrow(
                    """UPDATE dragonzpyder_goals
                       SET status='cancelled',next_run_at=NULL,updated_at=now()
                       WHERE goal_id=$1 AND source_app=$2 AND principal_hash=$3
                         AND status IN ('registered','awaiting_authorization','paused','cancelled')
                       RETURNING *""", _id(goal_id), source_app, principal,
                )
                if row is not None:
                    # Cancellation fences active claims in the SAME transaction.
                    # Even a late worker cannot commit a cancelled synthetic run.
                    await con.execute(
                        """UPDATE dragonzpyder_goal_runs
                           SET status='cancelled',claim_token=NULL,
                               lease_until=NULL,updated_at=now()
                           WHERE goal_id=$1 AND status IN
                             ('pending','running','awaiting_authorization')""",
                        _id(goal_id),
                    )
        return _serialize(row)

    async def list_runs(self, *, source_app: str, kind: str, user_id: str,
                        workspace_id: str | None, goal_id: str) -> list[dict]:
        principal = _principal(source_app=source_app, kind=kind,
                               user_id=user_id, workspace_id=workspace_id)
        async with self._pool.acquire() as con:
            # Validate owner even if no run exists. Return no cross-tenant clues.
            goal = await con.fetchval(
                """SELECT goal_id FROM dragonzpyder_goals
                   WHERE goal_id=$1 AND source_app=$2 AND principal_hash=$3""",
                _id(goal_id), source_app, principal,
            )
            if goal is None:
                raise LookupError("Goal is unavailable")
            rows = await con.fetch(
                """SELECT run_id,scheduled_for,status,attempts,
                          evidence_sha256,error_code
                   FROM dragonzpyder_goal_runs
                   WHERE goal_id=$1
                   ORDER BY scheduled_for DESC LIMIT 25""", goal,
            )
        return [
            {"run_id": str(row["run_id"]), "scheduled_for": row["scheduled_for"].isoformat(),
             "status": row["status"], "attempts": row["attempts"],
             "evidence_sha256": row["evidence_sha256"],
             "error_code": row["error_code"],
             "synthetic_only": (source_app == "internal_canary"
                                and principal == _principal(
                                    source_app="internal_canary", kind="personal",
                                    user_id="internal-staging-probe", workspace_id=None)),
             "objective_verified": False}
            for row in rows
        ]
