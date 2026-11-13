"""Durable, owner-scoped web tasks and sanitized execution-event journal.

Browser sessions are verified by DragonZpyder Web against Operly identity;
only the Web backend can invoke this service API. The browser never receives
Hatchet, OpenRouter, LangGraph, or service credentials.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from cryptography.fernet import Fernet

TASK_SCHEMA = """
CREATE TABLE IF NOT EXISTS dragonzpyder_ui_tasks (
    task_id uuid PRIMARY KEY,
    owner_hash char(64) NOT NULL,
    request_id uuid NOT NULL,
    kind text NOT NULL CHECK(kind IN ('probe','agent')),
    prompt_sha256 char(64) NOT NULL,
    prompt_ciphertext bytea NOT NULL,
    result_ciphertext bytea,
    status text NOT NULL CHECK(status IN
       ('queued','running','completed','incomplete','failed','cancelled')),
    claim_token uuid,
    lease_until timestamptz,
    attempts integer NOT NULL DEFAULT 0 CHECK(attempts BETWEEN 0 AND 2),
    objective_verified boolean NOT NULL DEFAULT false,
    trace_id varchar(64),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(owner_hash,request_id)
);
CREATE INDEX IF NOT EXISTS idx_dz_ui_tasks_owner
  ON dragonzpyder_ui_tasks(owner_hash,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_dz_ui_tasks_status
  ON dragonzpyder_ui_tasks(status,updated_at DESC);
CREATE TABLE IF NOT EXISTS dragonzpyder_ui_task_events (
    event_id bigserial PRIMARY KEY,
    task_id uuid NOT NULL REFERENCES dragonzpyder_ui_tasks(task_id)
       ON DELETE CASCADE,
    kind varchar(32) NOT NULL,
    message varchar(180) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_dz_ui_events_task
  ON dragonzpyder_ui_task_events(task_id,event_id);
"""

ALLOWED_KINDS = frozenset({"probe", "agent"})
ALLOWED_EVENTS = frozenset({
    "created","queued","started","model_started","model_finished",
    "tool_started","tool_finished","checkpoint","completed","incomplete",
    "failed","cancelled","dispatch_failed","recovered","info",
})


def owner_key(owner: str) -> str:
    if not isinstance(owner, str) or not 3 <= len(owner) <= 250:
        raise ValueError("Invalid authenticated user")
    # No prompt/user identity is written to the operator's event journal.
    return hashlib.sha256(
        json.dumps(["dragonzpyder-web-v1", owner], separators=(",", ":")).encode()
    ).hexdigest()


def uuid(value: str) -> UUID:
    result = UUID(value)
    if str(result) != value:
        raise ValueError("Noncanonical task UUID")
    return result


class ActivityStore:
    def __init__(self, pool, *, encryption_key: str):
        self.pool = pool
        self.cipher = Fernet(encryption_key.encode())

    @staticmethod
    def summary(row) -> dict:
        return {
            "task_id": str(row["task_id"]), "kind": row["kind"],
            "status": row["status"], "attempts": row["attempts"],
            "objective_verified": row["objective_verified"],
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat(),
            "trace_id": row["trace_id"],
        }

    async def create(self, *, owner: str, request_id: str,
                     kind: str, prompt: str) -> tuple[dict, bool]:
        identity = owner_key(owner)
        if kind not in ALLOWED_KINDS:
            raise ValueError("Invalid task kind")
        if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 5000:
            raise ValueError("Task must have a goal of at most 5000 characters")
        request = uuid(request_id)
        digest = hashlib.sha256(
            json.dumps([kind, prompt], ensure_ascii=True).encode()
        ).hexdigest()
        async with self.pool.acquire() as con:
            async with con.transaction():
                active = await con.fetchval(
                    """SELECT count(*) FROM dragonzpyder_ui_tasks
                       WHERE owner_hash=$1 AND status IN ('queued','running')""",
                    identity,
                )
                existing = await con.fetchrow(
                    """SELECT * FROM dragonzpyder_ui_tasks
                       WHERE owner_hash=$1 AND request_id=$2 FOR UPDATE""",
                    identity, request,
                )
                if existing is not None:
                    if existing["prompt_sha256"] != digest:
                        raise ValueError("Request identity already used for another task")
                    return self.summary(existing), False
                if active >= 3:
                    raise ValueError("At most three active tasks per account")
                task = await con.fetchrow(
                    """INSERT INTO dragonzpyder_ui_tasks
                       (task_id,owner_hash,request_id,kind,prompt_sha256,
                        prompt_ciphertext,status)
                       VALUES($1,$2,$3,$4,$5,$6,'queued') RETURNING *""",
                    uuid4(), identity, request, kind, digest,
                    self.cipher.encrypt(prompt.encode()),
                )
                await con.execute(
                    """INSERT INTO dragonzpyder_ui_task_events
                       (task_id,kind,message) VALUES($1,'created','Task accepted')""",
                    task["task_id"],
                )
        return self.summary(task), True

    async def append(self, task_id: str, kind: str, message: str) -> None:
        if kind not in ALLOWED_EVENTS or not isinstance(message, str) or not 1 <= len(message) <= 180:
            raise ValueError("Invalid sanitized execution event")
        if any(ord(c) < 32 or ord(c) == 127 for c in message):
            raise ValueError("Control character in execution event")
        async with self.pool.acquire() as con:
            await con.execute(
                """INSERT INTO dragonzpyder_ui_task_events(task_id,kind,message)
                   SELECT task_id,$2,$3 FROM dragonzpyder_ui_tasks
                   WHERE task_id=$1 AND status NOT IN('cancelled')
                     AND (SELECT count(*) FROM dragonzpyder_ui_task_events
                          WHERE task_id=$1)<250""",
                uuid(task_id), kind, message,
            )

    async def list(self, *, owner: str | None = None, admin: bool = False) -> list[dict]:
        if not admin and owner is None:
            raise PermissionError("Authenticated account required")
        identity = owner_key(owner) if not admin else None
        async with self.pool.acquire() as con:
            rows = await con.fetch(
                """SELECT task_id,kind,status,attempts,objective_verified,
                          created_at,updated_at,trace_id
                   FROM dragonzpyder_ui_tasks
                   WHERE ($1::text IS NULL OR owner_hash=$1)
                   ORDER BY created_at DESC LIMIT 50""",
                identity,
            )
        return [self.summary(row) for row in rows]

    async def get(self, *, owner: str | None, task_id: str,
                  admin: bool = False) -> dict:
        if not admin and owner is None:
            raise PermissionError("Authenticated account required")
        identity = owner_key(owner) if not admin else None
        async with self.pool.acquire() as con:
            row = await con.fetchrow(
                """SELECT * FROM dragonzpyder_ui_tasks
                   WHERE task_id=$1 AND ($2::text IS NULL OR owner_hash=$2)""",
                uuid(task_id), identity,
            )
            if row is None:
                raise LookupError("Task not available in this account")
            events = await con.fetch(
                """SELECT event_id,kind,message,created_at
                   FROM dragonzpyder_ui_task_events WHERE task_id=$1
                   ORDER BY event_id ASC LIMIT 250""",
                row["task_id"],
            )
        result = self.summary(row)
        result["events"] = [{
            "event_id": r["event_id"], "kind": r["kind"],
            "message": r["message"], "at": r["created_at"].isoformat()
        } for r in events]
        # Only the authenticated task owner may decrypt the result. Admin
        # can see operational metadata, never user prompts or answer contents.
        if not admin and row["result_ciphertext"] is not None:
            result["answer"] = self.cipher.decrypt(bytes(row["result_ciphertext"])).decode()
        return result

    async def cancel(self, *, owner: str, task_id: str) -> dict:
        identity = owner_key(owner)
        async with self.pool.acquire() as con:
            async with con.transaction():
                row = await con.fetchrow(
                    """UPDATE dragonzpyder_ui_tasks
                       SET status='cancelled',claim_token=NULL,lease_until=NULL,
                           updated_at=now()
                       WHERE task_id=$1 AND owner_hash=$2
                         AND status IN ('queued','running')
                       RETURNING *""",
                    uuid(task_id), identity,
                )
                if row is None:
                    row = await con.fetchrow(
                        """SELECT * FROM dragonzpyder_ui_tasks
                           WHERE task_id=$1 AND owner_hash=$2""",
                        uuid(task_id), identity,
                    )
                if row is None:
                    raise LookupError("Task not available in this account")
                if row["status"] == "cancelled":
                    await con.execute(
                        """INSERT INTO dragonzpyder_ui_task_events(task_id,kind,message)
                           SELECT $1,'cancelled','Cancelled by account owner'
                           WHERE NOT EXISTS (
                             SELECT 1 FROM dragonzpyder_ui_task_events
                             WHERE task_id=$1 AND kind='cancelled')""",
                        row["task_id"],
                    )
        return self.summary(row)

    async def claim(self, task_id: str) -> tuple[dict, str] | None:
        token = uuid4()
        async with self.pool.acquire() as con:
            row = await con.fetchrow(
                """UPDATE dragonzpyder_ui_tasks
                   SET status='running',claim_token=$2,attempts=attempts+1,
                       lease_until=now()+interval '6 minutes',updated_at=now()
                   WHERE task_id=$1 AND
                     (status='queued' OR
                       (status='running' AND lease_until < now() AND attempts < 2))
                   RETURNING *""",
                uuid(task_id), token,
            )
        return (row, str(token)) if row is not None else None

    async def finish(self, *, task_id: str, claim_token: str, status: str,
                     answer: str = "", trace_id: str | None = None) -> bool:
        if status not in ("completed", "incomplete", "failed"):
            raise ValueError("Invalid finish state")
        encrypted = self.cipher.encrypt(answer[:20000].encode()) if answer else None
        async with self.pool.acquire() as con:
            row = await con.fetchval(
                """UPDATE dragonzpyder_ui_tasks
                   SET status=$3,result_ciphertext=$4,trace_id=$5,
                       claim_token=NULL,lease_until=NULL,updated_at=now()
                   WHERE task_id=$1 AND claim_token=$2
                     AND status='running' AND lease_until>now()
                   RETURNING task_id""",
                uuid(task_id), uuid(claim_token), status, encrypted, trace_id,
            )
        return row is not None

    async def dispatch_failed(self, task_id: str) -> None:
        async with self.pool.acquire() as con:
            async with con.transaction():
                row = await con.fetchval(
                    """UPDATE dragonzpyder_ui_tasks SET status='failed',
                       updated_at=now() WHERE task_id=$1 AND status='queued'
                       RETURNING task_id""", uuid(task_id),
                )
                if row:
                    await con.execute(
                        """INSERT INTO dragonzpyder_ui_task_events(task_id,kind,message)
                           VALUES($1,'dispatch_failed','Queue dispatch failed')""",
                        row,
                    )
