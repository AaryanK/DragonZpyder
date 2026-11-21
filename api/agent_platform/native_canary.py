"""Isolated native-tool Hatchet canary for signed Personal conversations.

No Operly, MCP, model inference, external credentials, or remote tool calls
are used by the scheduled worker. This proves the native scheduling,
checkpoint/receipt DB and execution of an actual built-in LangChain tool.
This is a finite diagnostic, NOT the universal scheduler.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
import os
from uuid import UUID, uuid4

import asyncpg
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from .scientific_oracles import check_quadratic_gradient_step

SCHEMA = """
CREATE TABLE IF NOT EXISTS dz_native_canary_goals (
  goal_id text PRIMARY KEY,
  user_id text NOT NULL,
  conversation_id text NOT NULL,
  state text NOT NULL,
  next_sequence integer NOT NULL DEFAULT 0,
  blocked_reason text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS dz_native_canary_owner
  ON dz_native_canary_goals(user_id,conversation_id,created_at DESC);
CREATE TABLE IF NOT EXISTS dz_native_canary_receipts (
  goal_id text NOT NULL REFERENCES dz_native_canary_goals(goal_id),
  sequence integer NOT NULL CHECK(sequence BETWEEN 0 AND 1),
  tool_name text NOT NULL,
  result_sha256 text NOT NULL,
  result_data jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(goal_id,sequence)
);
"""

TOOL_ARGS = {
    "x": 2.0,
    "slope": 2.0,
    "intercept": -2.0,
    "learning_rate": 0.1,
    "proposed_next": 1.8,
}


class NativeCanaryWake(BaseModel):
    goal_id: str
    sequence: int = Field(ge=0, le=1)


def _canonical(value: str) -> str:
    try:
        parsed = str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Canonical signed identity required") from None
    if parsed != value:
        raise ValueError("Canonical signed identity required")
    return parsed


def require_native_canary() -> str:
    if os.getenv("DRAGONZPYDER_NATIVE_CANARY_ENABLED") != "1":
        raise RuntimeError("Native scheduler test is disabled")
    dsn = (os.getenv("DRAGONZPYDER_PERSONAL_MCP_DATABASE_URL")
           or os.getenv("DRAGONZPYDER_AGENT_DATABASE_URL", ""))
    if not dsn.startswith(("postgresql://", "postgres://")):
        raise RuntimeError("Native canary requires a durable PostgreSQL connection")
    return dsn


async def _pool():
    return await asyncpg.create_pool(
        dsn=require_native_canary(), min_size=1, max_size=2,
        timeout=10, command_timeout=30,
    )


async def execute_native_canary_wake(wake: NativeCanaryWake) -> dict:
    """Use the SAME registered mathematical tool as interactive chat.

    Lock + execute + persist is safe here because the tool is pure,
    deterministic and finishes without external effects. Do not copy this
    transaction pattern into a network/mutating MCP execution path.
    """
    _canonical(wake.goal_id)
    pool = await _pool()
    try:
        async with pool.acquire() as con:
            async with con.transaction():
                goal = await con.fetchrow(
                    """SELECT state,next_sequence FROM dz_native_canary_goals
                       WHERE goal_id=$1 FOR UPDATE""", wake.goal_id,
                )
                if goal is None:
                    return {"state": "not_found", "executed": False}
                if goal["state"] != "active":
                    return {"state": goal["state"], "executed": False}
                if goal["next_sequence"] > wake.sequence:
                    return {"state": "already_processed", "executed": False}
                if goal["next_sequence"] < wake.sequence:
                    await con.execute(
                        """UPDATE dz_native_canary_goals
                           SET state='blocked',blocked_reason='out_of_order',
                               updated_at=now() WHERE goal_id=$1""",
                        wake.goal_id,
                    )
                    return {"state": "blocked", "reason": "out_of_order",
                            "executed": False}

                # This must invoke the LangChain tool itself, not reproduce its
                # arithmetic using a second implementation.
                raw = await asyncio.wait_for(
                    check_quadratic_gradient_step.ainvoke(dict(TOOL_ARGS)),
                    timeout=10,
                )
                result = json.loads(raw)
                correct = (
                    result.get("arithmetic_valid") is True
                    and Decimal(result["gradient"]) == Decimal("2")
                    and Decimal(result["expected_next"]) == Decimal("1.8")
                    and result.get("correction_needed") is False
                )
                if not correct:
                    await con.execute(
                        """UPDATE dz_native_canary_goals
                           SET state='blocked',blocked_reason='native_math_mismatch',
                               updated_at=now() WHERE goal_id=$1""",
                        wake.goal_id,
                    )
                    return {"state": "blocked", "reason": "native_math_mismatch",
                            "executed": True}
                canonical_json = json.dumps(result, sort_keys=True)
                digest = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
                await con.execute(
                    """INSERT INTO dz_native_canary_receipts
                       (goal_id,sequence,tool_name,result_sha256,result_data)
                       VALUES($1,$2,$3,$4,$5::jsonb) ON CONFLICT DO NOTHING""",
                    wake.goal_id, wake.sequence,
                    "check_quadratic_gradient_step", digest, canonical_json,
                )
                state = "completed" if wake.sequence == 1 else "active"
                await con.execute(
                    """UPDATE dz_native_canary_goals
                       SET state=$2,next_sequence=$3,updated_at=now()
                       WHERE goal_id=$1""", wake.goal_id, state,
                    wake.sequence + 1,
                )
                return {
                    "state": state, "next_sequence": wake.sequence + 1,
                    "executed": True, "tool": "check_quadratic_gradient_step",
                    "result_sha256": digest, "verification": "postgres_receipt",
                }
    finally:
        await pool.close()


def make_native_canary_hatchet_task(hatchet):
    """Register one task type. Registration NEVER starts a schedule."""
    require_native_canary()

    @hatchet.task(
        name="dragonzpyder-native-tool-canary",
        input_validator=NativeCanaryWake,
        concurrency=1,
        retries=0,
        execution_timeout=timedelta(minutes=1),
    )
    async def native_wake(input: NativeCanaryWake, ctx) -> dict:
        return await execute_native_canary_wake(input)

    return native_wake


def native_canary_tools(*, user_id: str, conversation_id: str):
    """The signed Personal service call fixes ownership, not model arguments."""
    user_id, conversation_id = _canonical(user_id), _canonical(conversation_id)

    @tool("native_canary_start")
    async def native_canary_start() -> dict:
        """Schedule exactly two checks of DragonZpyder's BUILT-IN math tool.

        This is a cheap, read-only Hatchet+PostgreSQL diagnostic with no MCP,
        Operly calls, browser, external APIs or model inference at wake time.
        Returns a real goal ID; success requires TWO stored tool receipts.
        """
        require_native_canary()
        if not os.getenv("HATCHET_CLIENT_TOKEN"):
            raise RuntimeError("Private Hatchet client unavailable")
        pool = await _pool()
        try:
            async with pool.acquire() as con:
                await con.execute(SCHEMA)
                async with con.transaction():
                    await con.execute(
                        "SELECT pg_advisory_xact_lock(hashtext($1))", user_id,
                    )
                    existing = await con.fetchrow(
                        """SELECT goal_id,state FROM dz_native_canary_goals
                           WHERE user_id=$1 AND conversation_id=$2
                             AND state IN ('preparing','active')
                           ORDER BY created_at DESC LIMIT 1 FOR UPDATE""",
                        user_id, conversation_id,
                    )
                    if existing is not None:
                        return {"status": "already_scheduled",
                                "goal_id": existing["goal_id"],
                                "state": existing["state"]}
                    goal_id = str(uuid4())
                    await con.execute(
                        """INSERT INTO dz_native_canary_goals
                           (goal_id,user_id,conversation_id,state)
                           VALUES($1,$2,$3,'preparing')""",
                        goal_id, user_id, conversation_id,
                    )
            try:
                from hatchet_sdk import Hatchet
                hatchet = Hatchet()
                task = make_native_canary_hatchet_task(hatchet)
                first = datetime.now(timezone.utc) + timedelta(minutes=1)
                accepted = 0
                for sequence in (0, 1):
                    await task.aio_schedule(
                        run_at=first + timedelta(minutes=2 * sequence),
                        input=NativeCanaryWake(goal_id=goal_id,sequence=sequence),
                    )
                    accepted += 1
                async with pool.acquire() as con:
                    await con.execute(
                        """UPDATE dz_native_canary_goals SET state='active',
                           updated_at=now() WHERE goal_id=$1 AND state='preparing'""",
                        goal_id,
                    )
                return {
                    "status": "scheduled", "goal_id": goal_id,
                    "scheduled_wakes": accepted,
                    "first_wake_utc": first.isoformat(),
                    "second_wake_utc": (first + timedelta(minutes=2)).isoformat(),
                    "verified": False,
                }
            except Exception:
                async with pool.acquire() as con:
                    await con.execute(
                        """UPDATE dz_native_canary_goals SET state='blocked',
                           blocked_reason='dispatch_failed',updated_at=now()
                           WHERE goal_id=$1""",
                        goal_id,
                    )
                return {"status": "dispatch_failed", "goal_id": goal_id,
                        "verified": False}
        finally:
            await pool.close()

    @tool("native_canary_status")
    async def native_canary_status(goal_id: str = "") -> dict:
        """Inspect the two native Hatchet wake-ups and durable tool receipts.

        Omit goal_id to inspect the most recent test in this conversation.
        Never call a scheduled goal 'completed' without TWO actual receipts.
        """
        if goal_id:
            try:
                _canonical(goal_id)
            except ValueError:
                return {"status": "invalid_goal_id"}
        pool = await _pool()
        try:
            async with pool.acquire() as con:
                if goal_id:
                    row = await con.fetchrow(
                        """SELECT goal_id,state,blocked_reason,next_sequence
                           FROM dz_native_canary_goals WHERE goal_id=$1
                             AND user_id=$2 AND conversation_id=$3""",
                        goal_id,user_id,conversation_id,
                    )
                else:
                    row = await con.fetchrow(
                        """SELECT goal_id,state,blocked_reason,next_sequence
                           FROM dz_native_canary_goals WHERE user_id=$1
                             AND conversation_id=$2 ORDER BY created_at DESC
                             LIMIT 1""", user_id,conversation_id,
                    )
                if row is None:
                    return {"status": "not_found"}
                receipts = await con.fetch(
                    """SELECT sequence,tool_name,result_sha256,result_data,
                              created_at FROM dz_native_canary_receipts
                       WHERE goal_id=$1 ORDER BY sequence""",row["goal_id"],
                )
                return {
                    "goal_id": row["goal_id"],
                    "state": row["state"],
                    "blocked_reason": row["blocked_reason"],
                    "completed_wakes": len(receipts),
                    "total_wakes": 2,
                    "verified": (
                        row["state"] == "completed"
                        and row["next_sequence"] == 2
                        and [r["sequence"] for r in receipts] == [0,1]
                        and all(r["tool_name"] == "check_quadratic_gradient_step"
                                for r in receipts)
                    ),
                    "receipts": [
                        {"sequence": r["sequence"],
                         "tool": r["tool_name"],
                         "result_sha256": r["result_sha256"],
                         "output": (json.loads(r["result_data"])
                                    if isinstance(r["result_data"], str)
                                    else r["result_data"]),
                         "executed_at_utc": r["created_at"].isoformat()}
                        for r in receipts
                    ],
                }
        finally:
            await pool.close()

    @tool("native_canary_cancel")
    async def native_canary_cancel(goal_id: str) -> dict:
        """Cancel your own native canary; queued wakes then become no-ops."""
        try:
            _canonical(goal_id)
        except ValueError:
            return {"status": "invalid_goal_id"}
        pool = await _pool()
        try:
            async with pool.acquire() as con:
                result = await con.execute(
                    """UPDATE dz_native_canary_goals SET state='cancelled',
                       updated_at=now() WHERE goal_id=$1 AND user_id=$2
                       AND conversation_id=$3 AND state IN ('preparing','active')""",
                    goal_id,user_id,conversation_id,
                )
                return {"goal_id":goal_id,
                        "status":"cancelled" if result=="UPDATE 1" else "not_cancellable"}
        finally:
            await pool.close()

    return [native_canary_start,native_canary_status,native_canary_cancel]
