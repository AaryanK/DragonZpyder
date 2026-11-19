"""Staging proof: a real model chooses read-only tools over three durable wakes.

Not a general-purpose credentialed agent. This fixed synthetic objective
isolates scheduler, paid-model selection, local tool invocation, and PostgreSQL
recovery. One tool per wake. No Operly customer data or external mutations.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
from uuid import UUID, uuid4


from .local_tools import LocalToolRegistry

GOAL = "staging-worker-telemetry-v1"
MAX_STEPS = 3
MAX_ATTEMPTS = 2
INTERVAL = timedelta(minutes=5)
LEASE = timedelta(minutes=3)
TOOLS = {
    "read_utc_time": "time.now",
    "read_worker_memory": "system.memory",
    "read_worker_disk": "system.disk",
}
SCHEMA = """
CREATE TABLE IF NOT EXISTS dz_staging_horizon_v1 (
    goal_key text PRIMARY KEY,
    status text NOT NULL DEFAULT 'active',
    step_index integer NOT NULL DEFAULT 0,
    attempt_count integer NOT NULL DEFAULT 0,
    next_run_at timestamptz NOT NULL DEFAULT now(),
    claim_token uuid,
    lease_until timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT dz_horizon_status_check CHECK (status IN ('active','running','blocked','completed')),
    CONSTRAINT dz_horizon_index_check CHECK (step_index BETWEEN 0 AND 3)
);
CREATE TABLE IF NOT EXISTS dz_staging_horizon_receipts_v1 (
    goal_key text NOT NULL REFERENCES dz_staging_horizon_v1(goal_key),
    step_index integer NOT NULL,
    tool_name text NOT NULL,
    observed_at timestamptz NOT NULL,
    tool_result_sha256 char(64) NOT NULL,
    model_selected boolean NOT NULL,
    PRIMARY KEY(goal_key, step_index),
    UNIQUE(goal_key,tool_name)
);
"""


class HorizonError(RuntimeError):
    pass


def guard() -> tuple[str, str, str]:
    if os.getenv("DRAGONZPYDER_STAGE") != "staging" or os.getenv("DRAGONZPYDER_HORIZON_CANARY_ENABLED") != "1":
        raise HorizonError("Horizon canary is disabled outside staging")
    dsn = os.getenv("DRAGONZPYDER_HORIZON_DATABASE_URL", "")
    if not dsn.startswith(("postgresql://", "postgres://")):
        raise HorizonError("Dedicated durable PostgreSQL connection required")
    base = os.getenv("DRAGONZPYDER_AGENT_GATEWAY_BASE_URL", "").strip().rstrip("/")
    parsed = urlsplit(base)
    if (parsed.scheme != "http" or parsed.hostname != "dragonzpyder-gateway.railway.internal"
            or parsed.port != 8080 or parsed.path != "/internal/agent/v1"
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise HorizonError("Approved private staging model gateway required")
    secret = os.getenv("DRAGONZPYDER_AGENT_GATEWAY_TOKEN", "")
    if len(secret) < 32:
        raise HorizonError("Staging gateway service authorization missing")
    model = os.getenv("DRAGONZPYDER_HORIZON_MODEL_ID", "").strip()
    if not re.fullmatch(r"[a-zA-Z0-9_.:/-]{3,120}", model):
        raise HorizonError("Explicit model allowlist entry required")
    allowed = {
        x.strip() for x in os.getenv("DRAGONZPYDER_RUNTIME_ALLOWED_MODELS", "").split(",") if x.strip()
    }
    if model not in allowed:
        raise HorizonError("Model not in operator-approved allowlist")
    return dsn, base, model


def model_tools(already: set[str]) -> list[dict]:
    remaining = [name for name, original in TOOLS.items() if original not in already]
    return [{
        "type": "function",
        "function": {
            "name": name,
            "description": "Read a single harmless staging worker metric. No arguments.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        }
    } for name in remaining]


def accept_model_choice(data: object, already: set[str]) -> str:
    if not isinstance(data, dict):
        raise HorizonError("Invalid model tool selection")
    choices = data.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        raise HorizonError("Model must return one choice")
    item = choices[0]
    message = item.get("message") if isinstance(item, dict) else None
    calls = message.get("tool_calls") if isinstance(message, dict) else None
    if not isinstance(calls, list) or len(calls) != 1:
        raise HorizonError("Model must select exactly one tool")
    call = calls[0]
    function = call.get("function") if isinstance(call, dict) else None
    if not isinstance(function, dict):
        raise HorizonError("Model selected malformed tool")
    name = function.get("name")
    if name not in TOOLS or TOOLS[name] in already:
        raise HorizonError("Model selected forbidden or previously used tool")
    try:
        args = json.loads(function.get("arguments", "{}"))
    except (ValueError, TypeError):
        raise HorizonError("Invalid model tool arguments") from None
    if args != {}:
        raise HorizonError("Tool selection must have no arguments")
    return TOOLS[name]


async def select_with_model(base: str, model: str, *, already: set[str]) -> str:
    import httpx
    # Strictly bounded synthetic prompt; secrets, workspace and user content
    # never enter the model request.
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content":
                "You are a staging telemetry selector. Pick exactly one of the tools provided. "
                "Call the tool with an empty JSON object. Never explain or request another tool."},
            {"role": "user", "content":
                "For a three-run durable agent test, select one remaining safe telemetry tool."},
        ],
        "tools": model_tools(already),
        "tool_choice": "required",
        "parallel_tool_calls": False,
        "max_tokens": 160,
        "stream": False,
    }
    token = os.environ["DRAGONZPYDER_AGENT_GATEWAY_TOKEN"]
    try:
        async with httpx.AsyncClient(timeout=45, follow_redirects=False, trust_env=False) as client:
            response = await client.post(
                base + "/chat/completions",
                headers={"Authorization": "Bearer " + token,
                         "content-type": "application/json"},
                json=payload,
            )
            if response.status_code != 200 or len(response.content) > 24_000:
                raise HorizonError("Governed model gateway rejected bounded tool selection")
            data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HorizonError("Model selection transport or JSON failure") from exc
    return accept_model_choice(data, already)


def _hash_result(obj: dict) -> str:
    data = json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(data.encode()).hexdigest()


async def tick(pool, *, now: datetime | None = None, selector=None, local_registry=None) -> dict:
    """Execute at most one new real local tool call in one scheduled invocation.

    Lease + token fencing permit reclaim after worker death. A read-only tool
    may be re-read after a crash, but a step receipt is committed only once.
    """
    when = now or datetime.now(timezone.utc)
    if when.tzinfo is None:
        raise HorizonError("Scheduler time must be timezone aware")
    when = when.astimezone(timezone.utc)
    claim = uuid4()
    async with pool.acquire() as con:
        async with con.transaction():
            await con.execute(
                "INSERT INTO dz_staging_horizon_v1(goal_key) VALUES($1) ON CONFLICT DO NOTHING",
                GOAL,
            )
            current = await con.fetchrow(
                "SELECT * FROM dz_staging_horizon_v1 WHERE goal_key=$1 FOR UPDATE",
                GOAL,
            )
            if current["status"] in ("completed", "blocked"):
                return {"status": current["status"], "completed_steps": current["step_index"], "new_step": False}
            if current["status"] == "running" and current["lease_until"] and current["lease_until"] > when:
                return {"status": "running", "completed_steps": current["step_index"], "new_step": False}
            if current["next_run_at"] > when:
                return {"status": "waiting", "completed_steps": current["step_index"], "new_step": False}
            attempts = current["attempt_count"] + 1
            if attempts > MAX_ATTEMPTS:
                await con.execute(
                    "UPDATE dz_staging_horizon_v1 SET status='blocked',updated_at=$2 WHERE goal_key=$1",
                    GOAL, when,
                )
                return {"status": "blocked", "completed_steps": current["step_index"], "new_step": False}
            await con.execute(
                """UPDATE dz_staging_horizon_v1 SET status='running', attempt_count=$2,
                   claim_token=$3, lease_until=$4, updated_at=$5 WHERE goal_key=$1""",
                GOAL, attempts, claim, when + LEASE, when,
            )
            rows = await con.fetch(
                "SELECT tool_name FROM dz_staging_horizon_receipts_v1 WHERE goal_key=$1",
                GOAL,
            )
            already = {r["tool_name"] for r in rows}
            step = current["step_index"]
    try:
        choose = selector or select_with_model
        _, base, model = guard()
        tool_name = await choose(base, model, already=already)
        if tool_name not in TOOLS.values() or tool_name in already:
            raise HorizonError("Selection was not an unused allowlisted tool")
        tools = local_registry or LocalToolRegistry()
        result = tools.invoke(tool_name, {})
        if not isinstance(result, dict) or not result:
            raise HorizonError("Tool did not return a usable read-only observation")
        digest = _hash_result(result)
    except Exception:
        # Do not mark synthetic goals successful after model/tool errors.
        async with pool.acquire() as con:
            await con.execute(
                """UPDATE dz_staging_horizon_v1 SET status='active',
                   claim_token=NULL, lease_until=NULL, next_run_at=$3,
                   updated_at=$2 WHERE goal_key=$1 AND claim_token=$4
                   AND status='running'""",
                GOAL, when, when + INTERVAL, claim,
            )
        return {"status": "retry_scheduled", "completed_steps": step,
                "new_step": False, "error_code": "tool_or_model_failed"}
    async with pool.acquire() as con:
        async with con.transaction():
            # Fence stale claims after cancellation, new lease or restart.
            owned = await con.fetchrow(
                """SELECT step_index FROM dz_staging_horizon_v1
                   WHERE goal_key=$1 AND claim_token=$2 AND status='running'
                   AND lease_until > $3 FOR UPDATE""",
                GOAL, claim, when,
            )
            if not owned or owned["step_index"] != step:
                return {"status": "claim_lost", "completed_steps": step, "new_step": False}
            await con.execute(
                """INSERT INTO dz_staging_horizon_receipts_v1
                   (goal_key,step_index,tool_name,observed_at,tool_result_sha256,model_selected)
                   VALUES($1,$2,$3,$4,$5,TRUE)""",
                GOAL, step, tool_name, when, digest,
            )
            count = step + 1
            await con.execute(
                """UPDATE dz_staging_horizon_v1 SET step_index=$2,
                   status=$3, next_run_at=$4, attempt_count=0,
                   claim_token=NULL, lease_until=NULL, updated_at=$5
                   WHERE goal_key=$1""",
                GOAL, count, "completed" if count == MAX_STEPS else "active",
                when + INTERVAL, when,
            )
    return {"status": "completed" if count == MAX_STEPS else "progress",
            "completed_steps": count, "new_step": True,
            "tool_name": tool_name, "tool_result_sha256": digest,
            "model_selected": True}


async def run_once() -> dict:
    dsn, _, _ = guard()
    import asyncpg
    pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=3)
    try:
        async with pool.acquire() as con:
            await con.execute(SCHEMA)
        return await tick(pool)
    finally:
        await pool.close()


def main():
    import sys
    try:
        result = asyncio.run(run_once())
    except Exception as exc:
        print(json.dumps({"event": "dz_durable_horizon", "status": "blocked",
                          "error_type": type(exc).__name__}), flush=True)
        raise SystemExit(1) from None
    print(json.dumps({"event": "dz_durable_horizon", **result}, sort_keys=True), flush=True)
    if result.get("status") in {"blocked", "retry_scheduled", "claim_lost"}:
        sys.exit(1)


if __name__ == "__main__":
    main()
