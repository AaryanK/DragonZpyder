"""Signed-user native persistent-goal tools for DragonZpyder's Personal harness.

The signed Operly -> DragonZpyder service request fixes the identity. Model
arguments never contain user/session IDs, bearer credentials or Hatchet data.
Only short, read-only jobs are supported until audited recovery and mutation.
"""
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import asyncpg
from langchain_core.tools import tool

from .personal_wake import SCHEMA, PersonalWakeInput, make_personal_mcp_wake_task


def _canonical(value: str) -> str:
    try:
        result = str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise RuntimeError("Canonical signed Personal identity required") from None
    if result != value:
        raise RuntimeError("Canonical signed Personal identity required")
    return result


def _goal_db_dsn() -> str:
    if os.getenv("DRAGONZPYDER_PERSONAL_GOAL_TOOLS_ENABLED") != "1":
        raise RuntimeError("Personal goal management is disabled")
    dsn = os.getenv("DRAGONZPYDER_AGENT_DATABASE_URL", "")
    if not dsn.startswith(("postgresql://", "postgres://")):
        raise RuntimeError("Durable goal database is unavailable")
    return dsn


def _schedule_gate() -> str:
    dsn = _goal_db_dsn()
    if os.getenv("DRAGONZPYDER_PERSONAL_MCP_SCHEDULED_ENABLED") != "1":
        raise RuntimeError("Scheduled Personal MCP worker is not enabled")
    if os.getenv("DRAGONZPYDER_PERSONAL_MCP_MUTATIONS_ENABLED") == "1":
        raise RuntimeError("Scheduled MCP writes are not supported")
    if not os.getenv("HATCHET_CLIENT_TOKEN"):
        raise RuntimeError("Private Hatchet dispatch is unavailable")
    return dsn


def personal_goal_tools(*, user_id: str, session_id: str, conversation_id: str):
    """Generate tools bound to a verified service payload, NEVER model input."""
    user_id, session_id, conversation_id = (
        _canonical(value) for value in (user_id, session_id, conversation_id)
    )

    @tool("goal_schedule")
    async def goal_schedule(objective: str, interval_minutes: int = 2,
                            occurrences: int = 5) -> dict:
        """Schedule a short read-only recurring goal using authorized external tools.

        Use when a user asks you to continue checking or working later.
        Returns a real goal ID only after Hatchet accepted all scheduled wakes.
        Maximum 5 wake-ups, 2-10 minutes apart. Not for writes, approvals,
        arbitrary code, or promises of verified completion.
        """
        dsn = _schedule_gate()
        if not isinstance(objective, str) or not 1 <= len(objective.strip()) <= 12000:
            return {"status": "rejected", "reason": "invalid_objective"}
        if type(interval_minutes) is not int or not 2 <= interval_minutes <= 10:
            return {"status": "rejected", "reason": "interval_out_of_bounds"}
        if type(occurrences) is not int or not 2 <= occurrences <= 5:
            return {"status": "rejected", "reason": "occurrences_out_of_bounds"}
        objective = objective.strip()
        # The worker renews exact Personal authority and enforces read-only
        # capability scope independently for every wake-up.
        goal_id = str(uuid4())
        objective_hash = hashlib.sha256(objective.encode()).hexdigest()
        pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=2)
        try:
            # Operator-controlled bootstrap for installations where an
            # external SQL migration runner is not available. This is not
            # model-controlled, and no table is dropped or overwritten.
            if os.getenv("DRAGONZPYDER_PERSONAL_GOAL_SCHEMA_INSTALL_ALLOWED") == "1":
                async with pool.acquire() as schema_con:
                    await schema_con.execute(SCHEMA)
            async with pool.acquire() as con:
                async with con.transaction():
                    # Do not create several metered tasks for the same active chat.
                    existing = await con.fetchrow(
                        """SELECT goal_id,state FROM dz_personal_mcp_goals
                           WHERE user_id=$1 AND conversation_id=$2
                             AND state IN ('preparing','active','inflight','paused_budget')
                           ORDER BY created_at DESC LIMIT 1 FOR UPDATE""",
                        user_id, conversation_id,
                    )
                    if existing is not None:
                        return {"status": "existing_goal",
                                "goal_id": existing["goal_id"], "state": existing["state"]}
                    await con.execute(
                        """INSERT INTO dz_personal_mcp_goals
                          (goal_id,user_id,session_id,conversation_id,total_wakes,
                           objective_hash,state)
                           VALUES ($1,$2,$3,$4,$5,$6,'preparing')""",
                        goal_id,user_id,session_id,conversation_id,occurrences,objective_hash,
                    )
            try:
                from hatchet_sdk import Hatchet
                hatchet = Hatchet()
                wake_task = make_personal_mcp_wake_task(hatchet)
                # No sleep loops or in-memory timers. Every wake is a separate
                # Hatchet scheduled event; first one starts after one minute.
                base = datetime.now(timezone.utc) + timedelta(minutes=1)
                accepted = 0
                for seq in range(occurrences):
                    wake = PersonalWakeInput(
                        goal_id=goal_id,user_id=user_id,session_id=session_id,
                        conversation_id=conversation_id,sequence=seq,
                        total_wakes=occurrences,prompt=objective,
                    )
                    await wake_task.aio_schedule(
                        run_at=base + timedelta(minutes=seq * interval_minutes),
                        input=wake,
                    )
                    accepted += 1
                async with pool.acquire() as con:
                    await con.execute(
                        """UPDATE dz_personal_mcp_goals SET state='active',
                           updated_at=now() WHERE goal_id=$1 AND state='preparing'""",
                        goal_id,
                    )
            except Exception:
                # Fail closed: already-accepted tasks observe a non-active
                # state and will not call Operly. Do not pretend all dispatched.
                async with pool.acquire() as con:
                    await con.execute(
                        """UPDATE dz_personal_mcp_goals SET state='blocked',
                           updated_at=now() WHERE goal_id=$1""",goal_id,
                    )
                return {"status":"dispatch_failed","goal_id":goal_id,
                        "scheduled_wakes":accepted,"verified":False}
            return {"status":"scheduled","goal_id":goal_id,
                    "scheduled_wakes":accepted,"interval_minutes":interval_minutes,
                    "first_wake_utc":base.isoformat(),"verified":False}
        finally:
            await pool.close()

    @tool("goal_status")
    async def goal_status(goal_id: str) -> dict:
        """Read durable status and wake-up receipts of your own scheduled goal."""
        dsn = _goal_db_dsn()
        try:
            _canonical(goal_id)
        except RuntimeError:
            return {"status":"rejected","reason":"invalid_goal_id"}
        pool = await asyncpg.create_pool(dsn=dsn,min_size=1,max_size=2)
        try:
            async with pool.acquire() as con:
                row = await con.fetchrow(
                    """SELECT goal_id,state,next_sequence,total_wakes,updated_at
                       FROM dz_personal_mcp_goals WHERE goal_id=$1
                         AND user_id=$2 AND conversation_id=$3""",
                    goal_id,user_id,conversation_id,
                )
                if row is None:
                    return {"status":"not_found"}
                receipts = await con.fetch(
                    """SELECT sequence,status,tool_names,created_at
                       FROM dz_personal_mcp_receipts WHERE goal_id=$1
                       ORDER BY sequence""", goal_id,
                )
                return {"goal_id":goal_id,"state":row["state"],
                        "completed_wakes":row["next_sequence"],
                        "total_wakes":row["total_wakes"],
                        "receipts":[{"sequence":x["sequence"],"status":x["status"],
                                     "tool_names":x["tool_names"],
                                     "at":x["created_at"].isoformat()} for x in receipts],
                        "verified":row["state"] == "completed"
                                   and len(receipts) == row["total_wakes"]}
        finally:
            await pool.close()

    @tool("goal_cancel")
    async def goal_cancel(goal_id: str) -> dict:
        """Stop your own recurring goal. Future queued wake-ups become no-ops.

        A currently in-flight external read might already be executing.
        """
        dsn = _goal_db_dsn()
        try:
            _canonical(goal_id)
        except RuntimeError:
            return {"status":"rejected","reason":"invalid_goal_id"}
        pool = await asyncpg.create_pool(dsn=dsn,min_size=1,max_size=2)
        try:
            async with pool.acquire() as con:
                result = await con.execute(
                    """UPDATE dz_personal_mcp_goals SET state='cancelled',
                       updated_at=now() WHERE goal_id=$1 AND user_id=$2
                       AND conversation_id=$3 AND state IN ('preparing','active')""",
                    goal_id,user_id,conversation_id,
                )
                return {"status":"cancelled" if result == "UPDATE 1" else "not_cancellable",
                        "goal_id":goal_id}
        finally:
            await pool.close()

    return [goal_schedule, goal_status, goal_cancel]
