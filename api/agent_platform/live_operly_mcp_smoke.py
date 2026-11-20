"""ONE-SHOT live DragonZpyder -> real Operly MCP server acceptance.

Operly runs its actual MCP router and canonical Workspace Kernel in a PRIVATE
staging service with an isolated SQLite database and synthetic Workspace.
The model uses official langchain-mcp-adapters over real network HTTP, never
a fake transport. Upstream inference is capped by the DragonZpyder gateway.
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
from .operly_mcp_client import load_authorized_operly_mcp_tools
from .paid_tool_smoke import _gateway_guard_ready
from .runtime import model_client

log = logging.getLogger("dz.real_operly_mcp_smoke")
TABLE = "dz_staging_real_operly_mcp_v1"
RUN_KEY = "dz-real-mcp-live-20261120-v4-tool-alias"
EXPECTED_WORKSPACE = "DragonZpyder Isolated MCP Evaluation"
ALLOWED_TOOLS = frozenset({"workspace.describe", "workspace.modules.list"})
TOOL_ALIASES = frozenset({"operly_workspace_describe", "operly_workspace_modules_list"})
EXPECTED_HOST = "operly-private-mcp-acceptance-20.railway.internal"


def _preflight() -> tuple[str, str, str]:
    if any(os.getenv(k) != "1" for k in (
        "DRAGONZPYDER_AGENT_USE_GATEWAY",
        "DRAGONZPYDER_AGENT_PRODUCTION_MODE",
        "DRAGONZPYDER_AGENT_EVAL_ALLOW_PAID",
        "DRAGONZPYDER_OPERLY_TOOLS_ENABLED",
        "DRAGONZPYDER_OPERLY_MCP_ENABLED",
    )) or os.getenv("DRAGONZPYDER_STAGE") != "staging":
        raise RuntimeError("Private staging MCP test not authorized")
    parsed = urlsplit(os.getenv("DRAGONZPYDER_OPERLY_MCP_FIXTURE_URL", ""))
    if (parsed.scheme != "http" or parsed.hostname != EXPECTED_HOST
            or parsed.port != 8080 or parsed.path != "/mcp"
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise RuntimeError("Private staging Operly MCP origin not allowlisted")
    key = os.getenv("DRAGONZPYDER_OPERLY_MCP_FIXTURE_AUTH", "")
    if len(key) < 40:
        raise RuntimeError("Missing isolated staging fixture authority")
    dsn = os.getenv("DRAGONZPYDER_HARNESS_SMOKE_DATABASE_URL", "")
    if not dsn.startswith(("postgres://", "postgresql://")):
        raise RuntimeError("A dedicated PostgreSQL idempotency record is required")
    gateway = urlsplit(os.getenv("DRAGONZPYDER_AGENT_GATEWAY_BASE_URL", ""))
    if (gateway.scheme != "http"
            or gateway.hostname != "dragonzpyder-gateway.railway.internal"
            or gateway.port != 8080 or gateway.path != "/internal/agent/v1"):
        raise RuntimeError("Refused unapproved model inference endpoint")
    return parsed.geturl(), key, dsn


def _readback_verified(messages: list) -> tuple[bool, list[str]]:
    receipts = [m for m in messages if isinstance(m, ToolMessage)]
    tool_names = [str(m.name) for m in receipts]
    # Require one successful, structured receipt for each authorized tool.
    # Reject duplicates instead of allowing a later receipt to overwrite one.
    if len(receipts) != len(TOOL_ALIASES):
        return False, tool_names
    found = {}
    for receipt in receipts:
        if receipt.name not in TOOL_ALIASES or receipt.name in found:
            return False, tool_names
        if getattr(receipt, "status", "success") != "success":
            return False, tool_names
        try:
            payload = json.loads(receipt.content)
        except (TypeError, ValueError):
            return False, tool_names
        if not isinstance(payload, dict) or payload.get("error"):
            return False, tool_names
        found[receipt.name] = payload
    workspace = found.get("operly_workspace_describe", {})
    modules = found.get("operly_workspace_modules_list", {})
    described = workspace.get("name") == EXPECTED_WORKSPACE
    module_list = modules.get("modules")
    valid_modules = (isinstance(module_list, list)
                     and all(isinstance(item, dict)
                             and isinstance(item.get("key"), str)
                             and item["key"].strip()
                             and isinstance(item.get("name"), str)
                             and item["name"].strip()
                             for item in module_list))
    return bool(described and valid_modules and set(found) == TOOL_ALIASES), tool_names


def _has_terminal_ai_answer(messages: list) -> bool:
    if not messages:
        return False
    last = messages[-1]
    content = getattr(last, "content", "")
    return bool(getattr(last, "type", "") == "ai"
                and isinstance(content, str) and content.strip()
                and not getattr(last, "tool_calls", None))


async def _revoke_and_probe(url: str, fixture_secret: str, token: str) -> bool:
    """Bounded best-effort revocation; success requires server-confirmed denial."""
    origin = url.removesuffix("/mcp")
    async with httpx.AsyncClient(trust_env=False, timeout=5,
                                 follow_redirects=False) as http:
        revoke = await http.post(
            origin + "/_fixture/revoke",
            headers={"X-Fixture-Authority": fixture_secret},
        )
        if revoke.status_code != 200:
            return False
        after = await http.post(
            url,
            headers={"Authorization": "Bearer " + token,
                     "MCP-Protocol-Version": "2025-06-18"},
            json={"jsonrpc": "2.0", "id": 999, "method": "tools/list"},
        )
        return after.status_code == 401


async def _run() -> dict:
    import asyncpg
    url, fixture_secret, dsn = _preflight()
    if not await _gateway_guard_ready():
        return {"status": "blocked", "reason": "gateway_spend_cap_not_verified"}

    conn = await asyncpg.connect(dsn=dsn, timeout=8, command_timeout=8)
    try:
        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {TABLE} (
                run_key text PRIMARY KEY,
                state text NOT NULL,
                metrics jsonb,
                created_at timestamptz NOT NULL DEFAULT now()
            )
        """)
        claimed = await conn.fetchval(f"""
            INSERT INTO {TABLE}(run_key,state) VALUES($1,'reserved')
            ON CONFLICT DO NOTHING RETURNING run_key
        """, RUN_KEY)
        if not claimed:
            previous = await conn.fetchval(
                f"SELECT state FROM {TABLE} WHERE run_key=$1", RUN_KEY
            )
            return {"status": "already_reserved", "previous": previous}
    finally:
        await conn.close()

    metrics = {"status": "execution_failed", "verified": False}
    started = time.monotonic()
    model_graph = None
    token = None
    phase = "preauth"
    try:
        async with httpx.AsyncClient(trust_env=False, timeout=12,
                                     follow_redirects=False) as http:
            origin = url.removesuffix("/mcp")
            phase = "token_issue"
            auth = await http.post(
                origin + "/_fixture/auth",
                headers={"X-Fixture-Authority": fixture_secret},
            )
            if auth.status_code != 200 or len(auth.content) > 5000:
                raise RuntimeError("Private staging credential grant denied")
            token_data = auth.json()
            token = token_data.get("access_token")
            if not isinstance(token, str) or len(token) < 32:
                raise RuntimeError("Invalid staging access token")

            phase = "mcp_initialize"
            tools = await asyncio.wait_for(
                load_authorized_operly_mcp_tools(
                    url=url, access_token=token,
                    approved_tool_names=ALLOWED_TOOLS,
                    max_tools=2,
                ), timeout=30,
            )
            phase = "graph_construction"
            model_graph = build_frontier_agent(
                model_client(), MemorySaver(), delegated_tools=tools,
            )
            prompt = (
                "You are connected to an isolated Operly staging Workspace over MCP. "
                "Call the available MCP tools to find the exact workspace name and "
                "list its currently visible modules. Both tools are read-only and "
                "have already been authorized. Do not use subagents, write files, "
                "mutate data, or claim any data that was not returned by a tool. "
                "Summarize the observed workspace identity and modules."
            )
            phase = "graph_invoke"
            state = await asyncio.wait_for(model_graph.ainvoke(
                {"messages": [{"role": "user", "content": prompt}]},
                config={
                    "configurable": {"thread_id": RUN_KEY},
                    "recursion_limit": 64,
                },
            ), timeout=120)
            verified, names = _readback_verified(state.get("messages", []))
            # Tool receipts alone do not establish completed user intent.
            # A final assistant response is mandatory before claiming success.
            final_ai = _has_terminal_ai_answer(state.get("messages", []))
            verified = bool(verified and final_ai)
            metrics.update({
                "status": "passed" if verified else "insufficient_tool_evidence",
                "verified": verified,
                "tool_names": names[:16],
                "actual_tool_count": len(names),
                "final_ai": final_ai,
            })
    except Exception as exc:
        root = exc.__cause__ or exc
        metrics["status"] = "execution_failed"
        metrics["phase"] = phase
        metrics["exception_type"] = type(root).__name__
        errors = []
        def descend(error):
            if isinstance(error, BaseExceptionGroup):
                for child in error.exceptions:
                    descend(child)
            else:
                safe = str(error).split(chr(10), 1)[0][:100]
                if any(marker in safe.lower() for marker in (
                    "token", "bearer", "authorization", "secret", "http://", "https://"
                )):
                    safe = "[redacted]"
                errors.append({"type": type(error).__name__, "hint": safe})
        descend(exc)
        metrics["leaf_errors"] = errors[:5]
        if model_graph is not None:
            try:
                snapshot = await model_graph.aget_state({
                    "configurable": {"thread_id": RUN_KEY}
                })
                messages = snapshot.values.get("messages", [])
                metrics["checkpoint_tools"] = [
                    m.name for m in messages if isinstance(m, ToolMessage)
                ][:16]
                metrics["checkpoint_model_tool_requests"] = [
                    call.get("name", "")
                    for m in messages if getattr(m, "type", None) == "ai"
                    for call in (getattr(m, "tool_calls", None) or [])
                ][:16]
            except Exception as snap_error:
                metrics["checkpoint_error"] = type(snap_error).__name__
    finally:
        # Always attempt revocation after a token was issued, including failures
        # during MCP discovery, graph construction, and inference.
        if token is not None:
            try:
                metrics["revocation_enforced"] = await asyncio.wait_for(
                    _revoke_and_probe(url, fixture_secret, token), timeout=12,
                )
            except Exception as cleanup_error:
                metrics["revocation_enforced"] = False
                metrics["revocation_error_type"] = type(cleanup_error).__name__
            if not metrics["revocation_enforced"]:
                metrics["verified"] = False
                metrics["status"] = "revocation_not_verified"
        metrics["elapsed_s"] = round(time.monotonic() - started, 2)

    conn = await asyncpg.connect(dsn=dsn, timeout=8, command_timeout=8)
    try:
        await conn.execute(
            f"UPDATE {TABLE} SET state=$2, metrics=$3::jsonb WHERE run_key=$1",
            RUN_KEY, metrics["status"], json.dumps(metrics),
        )
    finally:
        await conn.close()
    return metrics


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    try:
        metrics = asyncio.run(_run())
    except Exception as exc:
        metrics = {"status": "refused", "exception_type": type(exc).__name__}
    print("DRAGONZPYDER_REAL_OPERLY_MCP_RESULT " + json.dumps(metrics, sort_keys=True))


if __name__ == "__main__":
    main()
