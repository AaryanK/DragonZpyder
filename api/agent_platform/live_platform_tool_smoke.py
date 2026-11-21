"""ONE-SHOT live-model -> Deep Agents -> scoped Operly-style broker acceptance.

Tests model selection against seeded/synthetic read-only platform records.
The broker HTTP transport is simulated; no real Operly account is contacted.
Only the approved private DragonZpyder metered gateway is used for inference.

Must run in STAGING with an enforced upstream $0.50 OpenRouter key cap.
A PostgreSQL reservation prevents paid repetition across redeploys.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from urllib.parse import urlsplit

import httpx
from langchain_core.messages import ToolMessage
from langgraph.checkpoint.memory import MemorySaver

from .harness import build_frontier_agent
from .operly_readonly_tools import OperlyReadOnlyTools
from .paid_tool_smoke import _gateway_guard_ready
from .runtime import model_client

log = logging.getLogger("dragonzpyder.live_platform_tool_smoke")
KEY = "staging-harness-live-platform-tools-20261120-v2-diagnostic"
TABLE = "dz_staging_live_platform_tools_v1"


def _gate() -> str:
    required = (
        "DRAGONZPYDER_STAGE",
        "DRAGONZPYDER_AGENT_USE_GATEWAY",
        "DRAGONZPYDER_AGENT_PRODUCTION_MODE",
        "DRAGONZPYDER_AGENT_EVAL_ALLOW_PAID",
        "DRAGONZPYDER_OPERLY_TOOLS_ENABLED",
    )
    if os.getenv("DRAGONZPYDER_STAGE") != "staging" or any(
        os.getenv(key) != "1" for key in required[1:]
    ):
        raise RuntimeError("Staging live-model tool test is disabled")
    base = os.getenv("DRAGONZPYDER_AGENT_GATEWAY_BASE_URL", "")
    parsed = urlsplit(base)
    if (
        parsed.scheme != "http" or parsed.hostname != "dragonzpyder-gateway.railway.internal"
        or parsed.port != 8080 or parsed.path != "/internal/agent/v1"
    ):
        raise RuntimeError("Unauthorized agent inference endpoint")
    dsn = os.getenv("DRAGONZPYDER_HARNESS_SMOKE_DATABASE_URL", "")
    if not dsn.startswith(("postgres://", "postgresql://")):
        raise RuntimeError("PostgreSQL reservation is required")
    return dsn


def _synthetic_handler(calls: list[dict]):
    """Read-only mock transport that implements existing Operly broker shapes."""
    specs = [
        {
            "id": "tasks.list", "description": "List the current user's open tasks",
            "risk": "read_only", "input_schema": {
                "type": "object", "properties": {
                    "status": {"type": "string"}, "limit": {"type": "integer"}
                },
            },
        },
        {
            "id": "system.runtime.status",
            "description": "Read the platform runtime status",
            "risk": "read_only",
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "id": "tasks.create",
            "description": "Create a task",
            "risk": "low",
            "input_schema": {"type": "object", "properties": {
                "title": {"type": "string"},
            }},
        },
    ]

    def handler(request: httpx.Request):
        body = json.loads(request.content)
        calls.append({
            "path": request.url.path,
            "capability": body.get("capability_id"),
        })
        if request.headers.get("Authorization") != "Bearer " + "t" * 48:
            return httpx.Response(401, json={"ok": False})
        if request.headers.get("X-Operly-Agent-Lease") != "synthetic-isolated-lease":
            return httpx.Response(403, json={"ok": False})
        if request.url.path.endswith("/search"):
            return httpx.Response(200, json={
                "source": "operly", "tools": specs,
            })
        if request.url.path.endswith("/execute"):
            if body.get("capability_id") == "tasks.list":
                return httpx.Response(200, json={
                    "ok": True, "result": {"tasks": [
                        {"id": "synth-1", "title": "Review project milestones",
                         "status": "open"},
                    ]},
                })
            if body.get("capability_id") == "system.runtime.status":
                return httpx.Response(200, json={
                    "ok": True, "result": {
                        "kernel_runtime_enabled": True,
                        "scope_kind": "personal",
                    },
                })
        return httpx.Response(403, json={
            "ok": False, "error_code": "forbidden",
        })
    return handler


def _terminal_ai_answer(messages) -> bool:
    """Require a nonempty final AI answer with no outstanding tool calls."""
    final = messages[-1] if messages else None
    return (
        getattr(final, "type", "") == "ai"
        and bool(str(getattr(final, "content", "")).strip())
        and not (getattr(final, "tool_calls", None) or [])
    )


async def _once() -> dict:
    import asyncpg

    dsn = _gate()
    if not await _gateway_guard_ready():
        return {"status": "blocked", "reason": "hard_provider_key_cap_not_verified"}

    conn = await asyncpg.connect(dsn=dsn, timeout=8, command_timeout=8)
    try:
        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {TABLE} (
                run_key text PRIMARY KEY,
                state text NOT NULL,
                metrics jsonb,
                created_at timestamptz DEFAULT now()
            )
        """)
        claimed = await conn.fetchval(f"""
            INSERT INTO {TABLE}(run_key,state) VALUES($1,'reserved')
            ON CONFLICT DO NOTHING RETURNING run_key
        """, KEY)
        if not claimed:
            state = await conn.fetchval(
                f"SELECT state FROM {TABLE} WHERE run_key=$1", KEY,
            )
            return {"status": "already_reserved", "previous_state": state}
    finally:
        await conn.close()

    started = time.monotonic()
    metrics = {"status": "failed", "verified": False}
    calls: list[dict] = []
    graph = None
    try:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(_synthetic_handler(calls)),
            trust_env=False,
        ) as http:
            adapter = OperlyReadOnlyTools(
                client=http, origin="https://operly.dragonzpyder.xyz",
                service_token="t" * 48,
                lease="synthetic-isolated-lease",
                max_calls=8,
            )
            model = model_client()
            graph = build_frontier_agent(
                model, MemorySaver(), delegated_tools=adapter.langchain_tools(),
            )
            prompt = (
                "This is an isolated simulated Operly platform, not any real user's data. "
                "Find my open tasks and inspect the platform's runtime status. "
                "Use the authorized discovery and execution tools to obtain both facts. "
                "Do not create, modify, or delete anything; no delegation. "
                "Answer only from observed tool outputs."
            )
            state = await asyncio.wait_for(graph.ainvoke(
                {"messages": [{"role": "user", "content": prompt}]},
                config={
                    "configurable": {"thread_id": KEY},
                    "recursion_limit": 60,
                },
            ), timeout=100)
        results = []
        tool_names = []
        for msg in state.get("messages", []):
            if not isinstance(msg, ToolMessage):
                continue
            tool_names.append(msg.name)
            if msg.name == "operly_execute":
                try:
                    datum = json.loads(msg.content)
                except (ValueError, TypeError):
                    continue
                if datum.get("ok") is True:
                    results.append(datum)
        by_name = {x["capability_id"]: x["result"] for x in results
                   if isinstance(x.get("capability_id"), str)}
        observed = set(by_name)
        read_only = all(x.get("capability") != "tasks.create" for x in calls)
        correct_tasks = (
            by_name.get("tasks.list", {}).get("tasks", [{}])[0].get("id")
            == "synth-1"
        ) if by_name.get("tasks.list", {}).get("tasks") else False
        correct_runtime = (
            by_name.get("system.runtime.status", {}).get("kernel_runtime_enabled")
            is True
        )
        final_ai = _terminal_ai_answer(state.get("messages", []))
        verified = (
            {"tasks.list", "system.runtime.status"}.issubset(observed)
            and read_only and correct_tasks and correct_runtime and final_ai
        )
        metrics.update({
            "status": "passed" if verified else "insufficient_tool_evidence",
            "verified": verified,
            "tool_names": tool_names[:20],
            "broker_calls": len(calls),
            "executed_capabilities": sorted(observed),
            "read_only": read_only,
            "final_ai": final_ai,
        })
    except Exception as exc:
        cause = exc.__cause__ or exc
        metrics["exception_type"] = type(cause).__name__
        metrics["status"] = "execution_failed"
        metrics["broker_calls"] = len(calls)
        metrics["attempted_capabilities"] = sorted({
            x["capability"] for x in calls if isinstance(x.get("capability"), str)
        })
        if graph is not None:
            try:
                snapshot = await graph.aget_state({
                    "configurable": {"thread_id": KEY}
                })
                messages = snapshot.values.get("messages", [])
                metrics["checkpoint_message_count"] = len(messages)
                metrics["checkpoint_tools"] = [
                    m.name for m in messages if isinstance(m, ToolMessage)
                ][:30]
                metrics["checkpoint_model_requested_tools"] = [
                    call.get("name", "") for m in messages if getattr(m, "type", None) == "ai"
                    for call in (getattr(m, "tool_calls", None) or [])
                ][:30]
            except Exception as evidence_error:
                metrics["checkpoint_error_type"] = type(evidence_error).__name__
    finally:
        metrics["elapsed_s"] = round(time.monotonic() - started, 2)
    conn = await asyncpg.connect(dsn=dsn, timeout=8, command_timeout=8)
    try:
        await conn.execute(
            f"UPDATE {TABLE} SET state=$2, metrics=$3::jsonb WHERE run_key=$1",
            KEY, metrics["status"], json.dumps(metrics),
        )
    finally:
        await conn.close()
    return metrics


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    try:
        result = asyncio.run(_once())
    except Exception as exc:
        result = {
            "status": "refused",
            "exception_type": type(exc).__name__,
        }
    print("DRAGONZPYDER_HARNESS_LIVE_TOOL_SMOKE " + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
