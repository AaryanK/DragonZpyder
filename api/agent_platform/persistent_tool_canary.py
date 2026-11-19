"""An isolated, bounded three-wake *real model* -> *real local tool* staging canary.

Runs from a five-minute Railway cron. PostgreSQL persists the objective, each
approved model choice and each tool receipt. An actual AIMessage.tool_calls
item is required: deterministic fallback is forbidden in the live path.

This tests one fixed infrastructure goal, NOT arbitrary user objectives or
Operly business access. No shell, outbound tool, user data, or credentials
ever enter a model prompt.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any

from .local_tools import LocalToolRegistry

GOAL_ID = "staging-worker-health-3-wake-v1"
GOAL_STEPS = ("time.now", "system.memory", "system.disk")
SCHEMA = """
CREATE TABLE IF NOT EXISTS dz_staging_long_horizon_goals (
    id text PRIMARY KEY,
    next_step int NOT NULL DEFAULT 0 CHECK (next_step BETWEEN 0 AND 3),
    state text NOT NULL DEFAULT 'active'
      CHECK (state IN ('active','completed','blocked','cancelled')),
    failure_count int NOT NULL DEFAULT 0 CHECK (failure_count BETWEEN 0 AND 3),
    last_bucket timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS dz_staging_long_horizon_receipts (
    goal_id text NOT NULL REFERENCES dz_staging_long_horizon_goals(id),
    step_index int NOT NULL CHECK (step_index BETWEEN 0 AND 2),
    bucket_start timestamptz NOT NULL,
    tool_name text NOT NULL,
    result_json jsonb NOT NULL,
    result_sha256 char(64) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (goal_id, step_index),
    UNIQUE (goal_id, bucket_start)
);
"""

class CanaryError(RuntimeError):
    pass


def gate() -> None:
    if (os.getenv("DRAGONZPYDER_STAGE") != "staging"
        or os.getenv("DRAGONZPYDER_LONG_HORIZON_CANARY_ENABLED") != "1"):
        raise CanaryError("Staging long-horizon canary is disabled")
    if os.getenv("DRAGONZPYDER_AGENT_USE_GATEWAY") != "1":
        raise CanaryError("Metered model gateway is mandatory")
    if os.getenv("DRAGONZPYDER_AGENT_PRODUCTION_MODE") != "1":
        raise CanaryError("Unmetered direct model calls are forbidden")
    dsn = os.getenv("DRAGONZPYDER_LONG_HORIZON_DATABASE_URL", "")
    if not dsn.startswith(("postgres://", "postgresql://")):
        raise CanaryError("Dedicated durable PostgreSQL is required")


def bucket_of(now: datetime) -> datetime:
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise CanaryError("Timezone-aware timestamp required")
    ts = int(now.timestamp())
    return datetime.fromtimestamp(ts // 300 * 300, tz=timezone.utc)


def approved_tools(remaining: tuple[str, ...] = GOAL_STEPS) -> list[dict]:
    if not remaining or any(name not in GOAL_STEPS for name in remaining):
        raise CanaryError("Tool catalog cannot exceed approved local allowlist")
    descriptions = {
        "time.now": "Read the actual worker's current UTC timestamp",
        "system.memory": "Read actual RAM utilization on the staging worker",
        "system.disk": "Read actual root filesystem utilization on the staging worker",
    }
    return [{
        "type": "function",
        "function": {
            "name": name.replace(".", "_"),
            "description": descriptions[name],
            "parameters": {"type": "object", "properties": {},
                           "additionalProperties": False},
        },
    } for name in remaining]


async def select_local_tool(model, remaining: tuple[str, ...]) -> str:
    """One real tool-choice message, no self-reported tool execution."""
    if not remaining:
        raise CanaryError("No remaining approved steps")
    specs = approved_tools(remaining)
    # Tool choice comes from an LLM, but does not confer permission. Server
    # independently checks name and empty arguments before any invocation.
    bound = model.bind_tools(specs, tool_choice="required")
    response = await asyncio.wait_for(bound.ainvoke([
        {"role": "system", "content": (
            "You are a restricted staging worker-health sensor selector. "
            "Make exactly one tool call using the approved tools. "
            "Do not write messages, execute code or request other tools."
        )},
        {"role": "user", "content": (
            "Continue a previously checkpointed infrastructure-health "
            "monitoring goal. Choose exactly one of the remaining tools: "
            + ", ".join(remaining) + ". Return only one empty-argument tool call."
        )},
    ]), timeout=45)
    calls = getattr(response, "tool_calls", None)
    if not isinstance(calls, list) or len(calls) != 1:
        raise CanaryError("Model failed to produce exactly one tool call")
    call = calls[0]
    if not isinstance(call, dict) or call.get("args") != {}:
        raise CanaryError("Model arguments are not an empty JSON object")
    name = call.get("name")
    allowed = {item.replace(".", "_"): item for item in remaining}
    if name not in allowed:
        raise CanaryError("Model selected an unavailable or unapproved tool")
    return allowed[name]


class PersistentToolCanary:
    def __init__(self, pool, *, model, registry=None):
        self.pool = pool
        self.model = model
        self.registry = registry or LocalToolRegistry()

    async def wake(self, *, now: datetime | None = None) -> dict[str, Any]:
        clock = now or datetime.now(timezone.utc)
        bucket = bucket_of(clock)
        # PostgreSQL row-level locking fences concurrent scheduled invocations.
        # The model call occurs under a short, bounded transaction. Only
        # read-only tools are available; failed work rolls back atomically.
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                goal = await connection.fetchrow(
                    """SELECT id,next_step,state,last_bucket,failure_count
                       FROM dz_staging_long_horizon_goals
                       WHERE id=$1 FOR UPDATE""", GOAL_ID,
                )
                if goal is None:
                    raise CanaryError("Goal not initialized; explicit migration required")
                if goal["state"] != "active":
                    return {"state":goal["state"],"tool_calls":0,"model_calls":0,
                            "next_step":goal["next_step"],"reason":"terminal"}
                if goal["last_bucket"] is not None and bucket <= goal["last_bucket"]:
                    return {"state":"sleeping","tool_calls":0,"model_calls":0,
                            "next_step":goal["next_step"],"reason":"same_interval"}
                step = int(goal["next_step"])
                if step >= len(GOAL_STEPS):
                    raise CanaryError("Invalid persisted active step index")
                # One task per wake. This selects a model tool each time, but
                # cannot reexecute any previously completed action.
                previous = await connection.fetch(
                    """SELECT tool_name FROM dz_staging_long_horizon_receipts
                       WHERE goal_id=$1 ORDER BY step_index""", GOAL_ID,
                )
                already_called = {row["tool_name"] for row in previous}
                remaining = tuple(name for name in GOAL_STEPS if name not in already_called)
                if len(already_called) != step or len(remaining) != len(GOAL_STEPS)-step:
                    raise CanaryError("Persisted tool history is inconsistent")
                try:
                    selected = await select_local_tool(self.model, remaining)
                    result = self.registry.invoke(selected, {})
                    if not isinstance(result, dict) or not result:
                        raise CanaryError("Local tool returned an invalid result")
                    serialized = json.dumps(result, sort_keys=True,
                                            separators=(",",":"), allow_nan=False)
                except Exception:
                    # Failure attempts are persisted without printing private
                    # provider exceptions, tool results, or credentials.
                    failed = goal["failure_count"] + 1
                    await connection.execute(
                        """UPDATE dz_staging_long_horizon_goals
                           SET failure_count=$2, state=$3,last_bucket=$4,updated_at=$5
                           WHERE id=$1""", GOAL_ID, failed,
                        "blocked" if failed >= 3 else "active",bucket,clock,
                    )
                    return {"state":"blocked" if failed>=3 else "retry_later",
                            "tool_calls":0,"model_calls":1,"next_step":step,
                            "reason":"model_or_tool_failed"}
                digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
                await connection.execute(
                    """INSERT INTO dz_staging_long_horizon_receipts
                       (goal_id,step_index,bucket_start,tool_name,result_json,result_sha256)
                       VALUES ($1,$2,$3,$4,$5::jsonb,$6)""",
                    GOAL_ID,step,bucket,selected,serialized,digest,
                )
                state = "completed" if step+1 == len(GOAL_STEPS) else "active"
                await connection.execute(
                    """UPDATE dz_staging_long_horizon_goals
                       SET next_step=$2,state=$3,last_bucket=$4,
                           failure_count=0,updated_at=$5 WHERE id=$1""",
                    GOAL_ID,step+1,state,bucket,clock,
                )
                # Compare the stored digest with data actually in the table.
                receipt = await connection.fetchrow(
                    """SELECT result_sha256,tool_name FROM dz_staging_long_horizon_receipts
                       WHERE goal_id=$1 AND step_index=$2""", GOAL_ID,step,
                )
                if receipt["result_sha256"] != digest or receipt["tool_name"] != selected:
                    raise CanaryError("PostgreSQL receipt verification failed")
                return {"state":state,"next_step":step+1,"last_tool":selected,
                        "receipt_sha256":digest,"model_calls":1,"tool_calls":1,
                        "verification":"database_readback",
                        "external_mutations":0}


async def provision(pool) -> None:
    gate()
    if os.getenv("DRAGONZPYDER_LONG_HORIZON_SCHEMA_INSTALL_ALLOWED") != "1":
        raise CanaryError("Staging schema installation not explicitly authorized")
    async with pool.acquire() as connection:
        async with connection.transaction():
            await connection.execute(SCHEMA)
            await connection.execute(
                """INSERT INTO dz_staging_long_horizon_goals(id) VALUES($1)
                   ON CONFLICT(id) DO NOTHING""",GOAL_ID,
            )


async def execute() -> dict:
    gate()
    import asyncpg
    from .runtime import model_client
    pool = await asyncpg.create_pool(
        dsn=os.environ["DRAGONZPYDER_LONG_HORIZON_DATABASE_URL"],
        min_size=1,max_size=2,timeout=10,command_timeout=60,
    )
    try:
        if os.getenv("DRAGONZPYDER_LONG_HORIZON_SCHEMA_INSTALL_ALLOWED") == "1":
            await provision(pool)
        # Reject a DB without the approved schema.
        async with pool.acquire() as con:
            if await con.fetchval(
                    "SELECT to_regclass('dz_staging_long_horizon_goals')") is None:
                raise CanaryError("Staging schema not installed")
        return await PersistentToolCanary(pool,model=model_client()).wake()
    finally:
        await pool.close()


def main() -> None:
    import asyncio
    result = asyncio.run(execute())
    # Exactly one structured log per cron execution, excluding raw tool output.
    print("DZ_LONG_HORIZON_RESULT " + json.dumps(result,sort_keys=True),
          flush=True)
    if result["state"] in ("blocked","retry_later"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
