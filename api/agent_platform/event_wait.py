"""Durable 'wait for an event' primitives owned by DragonZpyder.

The event is not an instruction to the language model. A typed monitor
observation is stored transactionally with its outbox wake, where it can
survive process restarts and repeated deliveries. No arbitrary webhooks
or user tools are executable through this adapter.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from .goal_store import _id, _principal
from .goal_reconciler import _canonical_time, utc_now

_MONITOR = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{2,63}$")
_CANARY = _principal(
    source_app="internal_canary", kind="personal",
    user_id="internal-staging-probe", workspace_id=None,
)
_LEASE = timedelta(seconds=90)


class EventWaitConflict(RuntimeError):
    pass


class EventWaitStore:
    def __init__(self, pool):
        self.pool = pool

    async def subscribe(
        self, *, source_app: str, kind: str, user_id: str,
        workspace_id: str | None, monitor_id: str, request_id: str,
    ) -> dict:
        if not isinstance(monitor_id, str) or not _MONITOR.fullmatch(monitor_id):
            raise ValueError("Invalid web monitor identifier")
        if source_app == "internal_canary" and not (
            kind == "personal" and user_id == "internal-staging-probe"
            and workspace_id is None
        ):
            raise ValueError("Internal synthetic event identity is reserved")
        principal = _principal(
            source_app=source_app, kind=kind, user_id=user_id,
            workspace_id=workspace_id,
        )
        async with self.pool.acquire() as con:
            async with con.transaction():
                row = await con.fetchrow(
                    """INSERT INTO dragonzpyder_event_waits
                       (wait_id,source_app,principal_hash,request_id,monitor_id,status)
                       VALUES ($1,$2,$3,$4,$5,'armed')
                       ON CONFLICT (source_app,principal_hash,request_id) DO NOTHING
                       RETURNING wait_id,monitor_id,status""",
                    uuid4(), source_app, principal, _id(request_id), monitor_id,
                )
                if row is None:
                    row = await con.fetchrow(
                        """SELECT wait_id,monitor_id,status
                           FROM dragonzpyder_event_waits
                           WHERE source_app=$1 AND principal_hash=$2
                             AND request_id=$3 FOR UPDATE""",
                        source_app, principal, _id(request_id),
                    )
                if row is None or row["monitor_id"] != monitor_id:
                    raise EventWaitConflict("Event wait request ID cannot be reused")
        return {"wait_id": str(row["wait_id"]), "status": row["status"],
                "monitor_id": row["monitor_id"], "execution_started": False}

    async def cancel(
        self, *, source_app: str, kind: str, user_id: str,
        workspace_id: str | None, wait_id: str,
    ) -> dict:
        principal = _principal(source_app=source_app, kind=kind,
                               user_id=user_id, workspace_id=workspace_id)
        async with self.pool.acquire() as con:
            async with con.transaction():
                row = await con.fetchrow(
                    """UPDATE dragonzpyder_event_waits
                       SET status='cancelled'
                       WHERE wait_id=$1 AND source_app=$2 AND principal_hash=$3
                       RETURNING wait_id,status""",
                    _id(wait_id), source_app, principal,
                )
                if row is None:
                    raise LookupError("Event wait unavailable")
                await con.execute(
                    """UPDATE dragonzpyder_event_wakes
                       SET status='cancelled', claim_token=NULL,
                           lease_until=NULL, updated_at=now()
                       WHERE wait_id=$1 AND status IN
                           ('pending','running','awaiting_authorization')""",
                    row["wait_id"],
                )
        return {"wait_id": str(row["wait_id"]), "status": "cancelled"}

    async def list_wakes(
        self, *, source_app: str, kind: str, user_id: str,
        workspace_id: str | None, wait_id: str,
    ) -> list[dict]:
        principal = _principal(source_app=source_app, kind=kind,
                               user_id=user_id, workspace_id=workspace_id)
        async with self.pool.acquire() as con:
            exists = await con.fetchval(
                """SELECT wait_id FROM dragonzpyder_event_waits
                   WHERE wait_id=$1 AND source_app=$2 AND principal_hash=$3""",
                _id(wait_id), source_app, principal,
            )
            if exists is None:
                raise LookupError("Event wait unavailable")
            rows = await con.fetch(
                """SELECT wake_id,status,attempts,evidence_sha256
                   FROM dragonzpyder_event_wakes WHERE wait_id=$1
                   ORDER BY updated_at DESC LIMIT 25""",
                exists,
            )
        return [
            {"wake_id": str(x["wake_id"]), "status": x["status"],
             "attempts": x["attempts"], "evidence_sha256": x["evidence_sha256"],
             "objective_verified": False}
            for x in rows
        ]

    async def claim_canary(self, *, now: datetime | None = None) -> dict | None:
        clock = _canonical_time(now or utc_now())
        token = uuid4()
        async with self.pool.acquire() as con:
            async with con.transaction():
                await con.execute(
                    """UPDATE dragonzpyder_event_wakes x
                       SET status='failed',claim_token=NULL,lease_until=NULL,
                           updated_at=$1
                       FROM dragonzpyder_event_waits w
                       WHERE x.wait_id=w.wait_id AND w.source_app='internal_canary'
                         AND w.principal_hash=$2 AND w.status='delivered'
                         AND x.status='running' AND x.lease_until <= $1
                         AND x.attempts>=3""", clock, _CANARY,
                )
                row = await con.fetchrow(
                    """WITH candidate AS (
                       SELECT x.wake_id FROM dragonzpyder_event_wakes x
                       JOIN dragonzpyder_event_waits w ON w.wait_id=x.wait_id
                       WHERE w.source_app='internal_canary'
                         AND w.principal_hash=$2 AND w.status='delivered'
                         AND x.attempts < 3
                         AND (x.status='pending' OR
                           (x.status='running' AND x.lease_until <= $1))
                       ORDER BY x.updated_at,x.wake_id
                       LIMIT 1 FOR UPDATE OF x SKIP LOCKED
                       )
                       UPDATE dragonzpyder_event_wakes x
                       SET status='running',attempts=x.attempts+1,
                           claim_token=$3,lease_until=$4,updated_at=$1
                       FROM candidate WHERE x.wake_id=candidate.wake_id
                       RETURNING x.wake_id,x.wait_id,x.event_id,x.claim_token,
                                 x.attempts""",
                    clock, _CANARY, token, clock + _LEASE,
                )
        return dict(row) if row is not None else None

    async def complete_canary(self, claim: dict, *,
                              now: datetime | None = None) -> dict:
        clock = _canonical_time(now or utc_now())
        evidence = hashlib.sha256(
            ("dz-event-wake-v1:" + str(claim["wait_id"])
             + ":" + str(claim["event_id"])).encode()
        ).hexdigest()
        async with self.pool.acquire() as con:
            row = await con.fetchrow(
                """UPDATE dragonzpyder_event_wakes x
                   SET status='completed',evidence_sha256=$3,
                       claim_token=NULL,lease_until=NULL,updated_at=$4
                   WHERE x.wake_id=$1 AND x.claim_token=$2 AND x.status='running'
                     AND x.lease_until>$4
                     AND EXISTS (
                       SELECT 1 FROM dragonzpyder_event_waits w
                       WHERE w.wait_id=x.wait_id AND w.status='delivered'
                         AND w.source_app='internal_canary'
                         AND w.principal_hash=$5
                     )
                   RETURNING x.wake_id,x.evidence_sha256,x.attempts""",
                claim["wake_id"], claim["claim_token"], evidence, clock, _CANARY,
            )
        if row is None:
            return {"status": "not_committed"}
        return {"wake_id": str(row["wake_id"]), "status": "completed",
                "evidence_sha256": row["evidence_sha256"],
                "attempts": row["attempts"], "synthetic_only": True,
                "objective_verified": False}

    async def drain_canary(self, *, now: datetime | None = None,
                           max_wakes: int = 3) -> list[dict]:
        if not 1 <= max_wakes <= 3:
            raise ValueError("Event wake budget exceeded")
        out = []
        for _ in range(max_wakes):
            claim = await self.claim_canary(now=now)
            if claim is None:
                break
            out.append(await self.complete_canary(claim, now=now))
        return out
