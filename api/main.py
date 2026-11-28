"""DragonZpyder's private, OpenAI-compatible model gateway (FastAPI).

The gateway authenticates backend callers; Operly remains responsible for
organisation, workspace, and user permissions. It never trusts browser cookies.
"""
import asyncio
import json
import logging
import hmac
import math
import os
import re
import time
from uuid import uuid4
from contextlib import asynccontextmanager, nullcontext
from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from observability import setup_telemetry, shutdown_telemetry, inference_span, span_trace_id
from usage_ledger import ledger, token_usage
from provider_gateway import provider_request
from agent_platform.gateway_protocol import validate_agent_body, validate_agent_response, AgentProtocolError
from agent_platform.router import router as agent_router
from identity.router import router as identity_public_keys_router
from identity.http_bridge import router as identity_http_bridge_router
from identity.browser_authorize import router as identity_browser_authorize_router
from identity.login_http import router as identity_login_router
from identity.provider_http import router as identity_provider_router
from identity.mobile_provider import router as identity_mobile_router
from identity.pending_proof_http import router as identity_pending_proof_router
from identity.native_recovery_http import router as native_recovery_router
from identity.active_recovery_http import router as active_recovery_router
from identity.relying_party_status import router as relying_party_status_router
from agent_platform.personal_bridge import router as operly_personal_bridge_router
from agent_platform.first_party_chat import router as first_party_chat_router
from agent_platform.personal_history_http import router as personal_history_router
from agent_platform.first_party_voice import router as first_party_voice_router, cleanup_expired_voice
from agent_platform.modular_voice import router as modular_voice_router, cleanup_expired_modular
from agent_platform.openrouter_voice import router as openrouter_voice_router, prepare_production_schema
from agent_platform.workspace_bridge import router as operly_workspace_bridge_router
from agent_platform.mcp_connection_http import router as mcp_connection_router
from agent_platform.openrouter_spend_guard import PaidTestBudgetError, require_paid_test_cap
from agent_platform.provider_pacing import AgentProviderPacer
from agent_platform.gateway_parent_budget import ParentBudgetGateway
from agent_platform.budget_reservations import BudgetExceeded

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_BYTES = 160_000
MODEL_PATTERN = re.compile(r"^[a-zA-Z0-9_.:/-]{3,100}$")


class GatewayError(Exception):
    def __init__(self, status: int, message: str, *, retry_after: int | None = None,
                 code: str | None = None):
        self.status = status
        self.message = message
        self.retry_after = retry_after
        self.code = code


class Runtime:
    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.hour_started = time.monotonic()
        self.calls = 0
        self.pending = 0
        self.concurrency = max(1, min(128, int(os.getenv("DRAGONZPYDER_API_CONCURRENCY", "12"))))

    async def charge(self) -> bool:
        async with self.lock:
            now = time.monotonic()
            if now - self.hour_started >= 3600:
                self.hour_started, self.calls = now, 0
            limit = max(1, min(1000, int(os.getenv("DRAGONZPYDER_RUNTIME_CALLS_PER_HOUR", "120"))))
            if self.calls >= limit:
                return False
            self.calls += 1
            return True

    async def enter(self) -> bool:
        async with self.lock:
            if self.pending >= self.concurrency:
                return False
            self.pending += 1
            return True

    async def leave(self) -> None:
        async with self.lock:
            self.pending = max(self.pending - 1, 0)


runtime = Runtime()
agent_pacer = AgentProviderPacer(concurrency=2, spacing_s=0.4)
parent_budget = ParentBudgetGateway()
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_telemetry()
    await ledger.open()
    await parent_budget.open()
    log.warning("Atomic parent-budget gateway status=%s",
                "ready" if parent_budget.active else "disabled")
    agent_runtime = None
    mcp_pool = None
    try:
        if os.getenv('DRAGONZPYDER_MCP_USER_CONNECTIONS_ENABLED') == '1':
            from agent_platform.mcp_connections import (require_gate, CredentialCipher,
                OAuthConnectionManager)
            import asyncpg
            require_gate()
            dsn = os.getenv('DRAGONZPYDER_MCP_DATABASE_URL', '')
            if not dsn.startswith(('postgres://', 'postgresql://')):
                raise RuntimeError('Dedicated MCP credential PostgreSQL is required')
            mcp_pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5,
                                                  command_timeout=20)
            app.state.mcp_connections = OAuthConnectionManager(mcp_pool, CredentialCipher())
        if os.getenv("DRAGONZPYDER_AGENTS_ENABLED") == "1":
            from agent_platform.runtime import AgentRuntime
            agent_runtime = AgentRuntime()
            await agent_runtime.start()
            app.state.agent_runtime = agent_runtime
        app.state.personal_memory_ready=False
        if (agent_runtime is not None and os.getenv("DRAGONZPYDER_FIRST_PARTY_CHAT_ENABLED")=="1"
                and os.getenv("DRAGONZPYDER_IDENTITY_HTTP_ENABLED")=="1"):
            try:
                from agent_platform.first_party_chat import _conversation_db
                from agent_platform.memory import prepare_native_memory
                async with asyncio.timeout(10):
                    async with _conversation_db() as db:
                        await prepare_native_memory(db)
                app.state.personal_memory_ready=True
                log.info("Personal memory storage ready")
            except Exception:
                log.warning("Personal memory storage unavailable; ordinary chat unaffected")
        async with httpx.AsyncClient(timeout=90.0, follow_redirects=False) as client:
            app.state.http = client
            if (os.getenv("RAILWAY_ENVIRONMENT_NAME") == "staging" and
                    os.getenv("DRAGONZPYDER_STAGING_PAID_TEST_CAP_USD") == "0.50"):
                try:
                    cap, remaining = await require_paid_test_cap(
                        client, os.getenv("OPENROUTER_API_KEY", "")
                    )
                except PaidTestBudgetError as error:
                    # This is a static, authored reason code: no key, provider
                    # payload, provider user ID or prompt is emitted.
                    log.warning("Staging OpenRouter cap preflight=%s", str(error))
                else:
                    log.warning(
                        "Staging OpenRouter cap preflight=verified limit_usd=%s remaining_usd=%s",
                        cap, remaining,
                    )
            await prepare_production_schema()
            voice_cleanup = asyncio.create_task(cleanup_expired_voice(client))
            modular_cleanup = asyncio.create_task(cleanup_expired_modular())
            try:
                yield
            finally:
                voice_cleanup.cancel()
                modular_cleanup.cancel()
                await asyncio.gather(voice_cleanup, modular_cleanup, return_exceptions=True)
    finally:
        if mcp_pool is not None:
            await mcp_pool.close()
        if agent_runtime is not None:
            await agent_runtime.close()
        await parent_budget.close()
        await ledger.close()
        shutdown_telemetry()


app = FastAPI(title="DragonZpyder API", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
app.include_router(identity_public_keys_router)
app.include_router(identity_http_bridge_router)
app.include_router(identity_browser_authorize_router)
app.include_router(identity_login_router)
app.include_router(identity_provider_router)
app.include_router(identity_mobile_router)
app.include_router(identity_pending_proof_router)
app.include_router(native_recovery_router)
app.include_router(active_recovery_router)
app.include_router(relying_party_status_router)
app.include_router(agent_router)
app.include_router(operly_personal_bridge_router)
app.include_router(first_party_chat_router)
from agent_platform.artifact_http import router as artifact_router
app.include_router(artifact_router)
app.include_router(personal_history_router)
app.include_router(first_party_voice_router)
app.include_router(modular_voice_router)
app.include_router(openrouter_voice_router)
app.state.provider_runtime = runtime
from agent_platform.native_workflows import router as native_workflows_router
app.include_router(native_workflows_router)
app.include_router(operly_workspace_bridge_router)
app.include_router(mcp_connection_router)


@app.middleware("http")
async def headers(request: Request, call_next):
    # Direct native/bridge calls bypass the browser proxy. Bound the JSON body
    # before FastAPI parses base64; require length framing for audio turns.
    if request.method=="POST" and re.fullmatch(r"/v2/personal/voice/(?:sessions|openrouter)/[0-9a-f-]{36}/turn",request.url.path):
        length=request.headers.get("content-length","")
        if request.headers.get("transfer-encoding") or not re.fullmatch(r"[0-9]{1,8}",length):
            return JSONResponse({"detail":"Voice turn requires bounded Content-Length"},status_code=411,headers={"cache-control":"no-store"})
        if int(length)>7_700_000:
            return JSONResponse({"detail":"Voice utterance exceeds bound"},status_code=413,headers={"cache-control":"no-store"})
    response = await call_next(request)
    response.headers["x-content-type-options"] = "nosniff"
    response.headers["referrer-policy"] = "no-referrer"
    response.headers["cache-control"] = "no-store"
    # Do not grant credentialed browser CORS to the private inference API.
    response.headers["access-control-allow-origin"] = "null"
    return response


def denied(status: int, message: str, *, code: str | None = None) -> JSONResponse:
    return JSONResponse({"error": {"message": message, "type": "dragonzpyder_inference_error", "code": code if code is not None else status}}, status_code=status)


def models() -> list[str]:
    raw = os.getenv("DRAGONZPYDER_RUNTIME_ALLOWED_MODELS", "openai/gpt-oss-120b")
    return list(dict.fromkeys(x for item in raw.split(",") if (x := item.strip()) and MODEL_PATTERN.fullmatch(x)))[:20]


def caller_identity(request: Request) -> str | None:
    """Derive the app ID from an operator-issued secret, never a browser header."""
    header = request.headers.get("authorization", "")
    if not header.startswith("Bearer "):
        return None
    bearer = header[7:]
    # A separately rotated token authenticates only the private agent
    # inference protocol. Do not grant provider, admin or legacy API access.
    dedicated_agent = os.getenv("DRAGONZPYDER_AGENT_GATEWAY_SERVICE_TOKEN", "")
    if (request.url.path.startswith("/internal/agent/v1/")
            and os.getenv("DRAGONZPYDER_AGENT_TOOL_CALLS_ENABLED") == "1"
            and len(dedicated_agent) >= 40
            and hmac.compare_digest(bearer, dedicated_agent)):
        return "agent-runtime"
    legacy = os.getenv("DRAGONZPYDER_RUNTIME_TOKEN", "")
    if len(legacy) >= 32 and hmac.compare_digest(bearer, legacy):
        return "legacy"
    try:
        keys = json.loads(os.getenv("DRAGONZPYDER_APP_KEYS_JSON", "{}"))
    except ValueError:
        return None
    if not isinstance(keys, dict):
        return None
    for app_id, token in keys.items():
        if (isinstance(app_id, str) and re.fullmatch(r"[a-z0-9_-]{2,60}", app_id)
                and isinstance(token, str) and len(token) >= 32
                and hmac.compare_digest(bearer, token)):
            return app_id
    return None


def authorized(request: Request) -> bool:
    return caller_identity(request) is not None


def admin_authorized(request: Request) -> bool:
    secret = os.getenv("DRAGONZPYDER_ADMIN_TOKEN", "")
    header = request.headers.get("authorization", "")
    return (len(secret) >= 40 and header.startswith("Bearer ") and
            hmac.compare_digest(header[7:], secret))


def valid_body(value: Any) -> dict:
    if not isinstance(value, dict):
        raise GatewayError(400, "Invalid request")
    model = value.get("model")
    if not isinstance(model, str) or model not in models():
        raise GatewayError(403, "Selected model is not enabled by DragonZpyder")
    messages = value.get("messages")
    if not isinstance(messages, list) or not 1 <= len(messages) <= 24:
        raise GatewayError(400, "Invalid message count")
    sanitized = []
    total = 0
    for item in messages:
        if (not isinstance(item, dict) or item.get("role") not in
                ("system", "developer", "user", "assistant") or not isinstance(item.get("content"), str)):
            raise GatewayError(400, "Unsupported role or message content")
        content = item["content"]
        if len(content) > 30000:
            raise GatewayError(413, "Individual message is too long")
        total += len(content)
        sanitized.append({"role": item["role"], "content": content})
    if total > 100000:
        raise GatewayError(413, "Conversation exceeds model input budget")
    max_tokens = value.get("max_tokens", 1200)
    if type(max_tokens) is not int or not 1 <= max_tokens <= 4096:
        raise GatewayError(400, "Output token limit must be 1–4096")
    if any(value.get(k) for k in ("tools", "tool_choice", "stream")):
        raise GatewayError(400, "Tool calling and streaming require separate scoped APIs")
    temperature = value.get("temperature", 0.2)
    if type(temperature) not in (float, int) or not math.isfinite(temperature) or not 0 <= temperature <= 1.5:
        raise GatewayError(400, "Unsupported temperature")
    body = {"model": model, "messages": sanitized, "max_tokens": max_tokens,
            "temperature": temperature, "stream": False}
    if "response_format" in value:
        if value["response_format"] != {"type": "json_object"}:
            raise GatewayError(400, "Only json_object response format is supported")
        body["response_format"] = {"type": "json_object"}
    return body


@app.get("/healthz")
async def healthz():
    configured = bool(os.getenv("DRAGONZPYDER_RUNTIME_TOKEN") and os.getenv("OPENROUTER_API_KEY"))
    return JSONResponse({"service": "dragonzpyder-api", "status": "ready" if configured else "unconfigured"},
                        status_code=200 if configured else 503)



ADMIN_CONFIG_FLAGS = (
    "DRAGONZPYDER_AGENTS_ENABLED",
    "DRAGONZPYDER_FIRST_PARTY_CHAT_ENABLED",
    "DRAGONZPYDER_IDENTITY_HTTP_ENABLED",
    "DRAGONZPYDER_AGENT_HARNESS_V2",
    "DRAGONZPYDER_AGENT_USE_GATEWAY",
    "DRAGONZPYDER_AGENT_PARALLEL_GATEWAY_ENABLED",
    "DRAGONZPYDER_AGENT_WEB_SEARCH_ENABLED",
    "DRAGONZPYDER_AGENT_WEB_FETCH_ENABLED",
    "DRAGONZPYDER_AGENT_ARTIFACTS_ENABLED",
    "DRAGONZPYDER_FIRST_PARTY_COMPUTER_ENABLED",
    "DRAGONZPYDER_FIRST_PARTY_REQUEST_LEDGER_ENABLED",
    "DRAGONZPYDER_FIRST_PARTY_STREAM_ENABLED",
    "DRAGONZPYDER_NATIVE_DURABLE_WORKFLOWS_ENABLED",
    "DRAGONZPYDER_EXECUTION_GRAPH_ENABLED",
    "DRAGONZPYDER_PERSONAL_MCP_SCHEDULED_ENABLED",
    "DRAGONZPYDER_PERSONAL_GOAL_CONTROLLER_ENABLED",
    "DRAGONZPYDER_FIRST_PARTY_GOAL_MANAGEMENT_ENABLED",
    "DRAGONZPYDER_MCP_USER_CONNECTIONS_ENABLED",
    "DRAGONZPYDER_NATIVE_MCP_OAUTH_ENABLED",
    "DRAGONZPYDER_MCP_EGRESS_FIREWALL_ENFORCED",
    "DRAGONZPYDER_MCP_USER_CONNECTIONS_PRODUCTION_APPROVED",
    "DRAGONZPYDER_MCP_PROGRAMMATIC_READS_ENABLED",
    "DRAGONZPYDER_AGENT_QUICKJS_ENABLED",
    "DRAGONZPYDER_ADAPTIVE_ROUTING_ENABLED",
    "DRAGONZPYDER_AGENT_MEDIA_ENABLED",
    "DRAGONZPYDER_NATIVE_VOICE_ENABLED",
    "DRAGONZPYDER_NATIVE_VOICE_AGENT_ENABLED",
    "DRAGONZPYDER_FIRST_PARTY_WEB_CUTOVER_ENABLED",
    "DRAGONZPYDER_AGENT_WORKER_ALLOWED",
    "DRAGONZPYDER_WEB_MONITOR_ENABLED",
    "DRAGONZPYDER_OPERLY_TOOLS_ENABLED",
    "DRAGONZPYDER_PERSONAL_MEMORY_RECALL_ENABLED",
)


def admin_runtime_config(request: Request):
    """Only report allowlisted non-secret booleans from this running process."""
    values = {}
    for name in ADMIN_CONFIG_FLAGS:
        value = os.getenv(name)
        values[name] = ("default_on" if name.endswith("PERSONAL_MEMORY_RECALL_ENABLED") else "unset") if value is None else (
            "on" if value == "1" else "off" if value == "0" else "other")
    return {"flags": values,
            "deployed_sha": os.getenv("RAILWAY_GIT_COMMIT_SHA"),
            "dependencies": {name: bool(os.getenv(name)) for name in (
                "HATCHET_CLIENT_TOKEN", "DRAGONZPYDER_AGENT_DATABASE_URL",
                "DRAGONZPYDER_MCP_DATABASE_URL", "DRAGONZPYDER_MCP_FERNET_KEYS",
                "DRAGONZPYDER_SEARXNG_ORIGIN", "DRAGONZPYDER_BRAVE_SEARCH_API_KEY",
                "DRAGONZPYDER_MEMORY_DATABASE_URL", "DRAGONZPYDER_ARTIFACT_KEY_B64",
                "DRAGONZPYDER_COMPUTER_RUNNER_URL", "DRAGONZPYDER_NATIVE_DURABLE_MAX_USD")},
            "native_memory_storage_ready": bool(getattr(request.app.state, "personal_memory_ready", False)),
            "mcp_initialized": getattr(request.app.state, "mcp_connections", None) is not None,
            "agent_initialized": getattr(request.app.state, "agent_runtime", None) is not None}


async def admin_identity_activity(days: int):
    """Count visible non-test identities and live sessions; never select PII."""
    from identity.http_bridge import _identity_db
    try:
        async with asyncio.timeout(10):
            async with _identity_db() as db:
                async with db.transaction(readonly=True):
                    accounts = await db.fetchrow("""SELECT COUNT(*)::int AS total_accounts,
                        COUNT(*) FILTER (WHERE status='active' AND source_active)::int AS active_accounts,
                        COUNT(*) FILTER (WHERE status='pending')::int AS pending_accounts,
                        COUNT(*) FILTER (WHERE status='disabled')::int AS disabled_accounts,
                        COUNT(*) FILTER (WHERE identity_origin='native_google'
                          AND created_at >= now()-($1::int * interval '1 day'))::int AS native_signups
                        FROM identity_accounts WHERE identity_origin <> 'operator_test'""", days)
                    sessions = await db.fetchrow("""SELECT COUNT(*)::int AS live_sessions,
                        COUNT(DISTINCT s.subject)::int AS session_holders
                        FROM identity_browser_sessions s JOIN identity_accounts a ON a.subject=s.subject
                        WHERE a.identity_origin <> 'operator_test' AND a.status='active' AND a.source_active
                          AND s.revoked_at IS NULL AND s.expires_at > now()""")
        return {"state": "available", "accounts": dict(accounts), "sessions": dict(sessions)}
    except Exception:
        return {"state": "unavailable", "accounts": None, "sessions": None}


async def admin_platform_activity(request: Request, days: int):
    """Bounded read-only product aggregates from authoritative native stores.

    Never query account credentials, conversation titles, messages, checkpoint
    state, tool arguments, memory contents, or encrypted payload escrow.
    Each source reports unavailability separately instead of inventing zeros.
    """
    from agent_platform.first_party_chat import _conversation_db, status as personal_status

    async def query_rows(sql, *args):
        try:
            async with asyncio.timeout(8):
                async with _conversation_db() as db:
                    async with db.transaction(readonly=True):
                        records = await db.fetch(sql, *args)
                        return {"state": "available", "rows": [dict(r) for r in records]}
        except Exception:
            # Do not leak DB errors, schemas, DSNs, or customer data.
            return {"state": "unavailable", "rows": []}

    # SQL is static and parameters are bounded by the caller. UTC bucketing.
    requests, daily, conversations, workflows, goals, memory, identity_activity, owners = await asyncio.gather(
        query_rows("""SELECT status, COUNT(*)::int AS count,
            COUNT(*) FILTER (WHERE cancel_requested)::int AS cancellation_requested
            FROM dz_first_party_chat_requests
            WHERE created_at >= now() - ($1::int * interval '1 day')
            GROUP BY status ORDER BY status""", days),
        query_rows("""SELECT to_char(created_at AT TIME ZONE 'UTC', 'YYYY-MM-DD') AS day,
            COUNT(*)::int AS requests,
            COUNT(DISTINCT owner_id)::int AS active_users,
            COUNT(*) FILTER (WHERE status='completed')::int AS completed
            FROM dz_first_party_chat_requests
            WHERE created_at >= now() - ($1::int * interval '1 day')
            GROUP BY 1 ORDER BY 1 LIMIT 91""", days),
        query_rows("""SELECT COUNT(*)::int AS active_conversations,
            COUNT(DISTINCT owner_id)::int AS conversation_owners
            FROM dz_first_party_conversations
            WHERE updated_at >= now() - ($1::int * interval '1 day')""", days),
        query_rows("""SELECT state, COUNT(*)::int AS count FROM dz_native_workflows
            WHERE updated_at >= now() - ($1::int * interval '1 day') OR state IN
            ('preparing','active','inflight','uncertain')
            GROUP BY state ORDER BY state""", days),
        query_rows("""SELECT state, COUNT(*)::int AS count FROM dz_personal_mcp_goals
            WHERE updated_at >= now() - ($1::int * interval '1 day') OR state='active'
            GROUP BY state ORDER BY state""", days),
        query_rows("""SELECT COUNT(*)::int AS saved_entries,
            COUNT(DISTINCT owner_id)::int AS memory_owners,
            COUNT(*) FILTER (WHERE recall_in_chat)::int AS recall_enabled_entries
            FROM dz_personal_memory WHERE created_at >= now() - ($1::int * interval '1 day')""", days),
        admin_identity_activity(days),
        query_rows("""SELECT COUNT(DISTINCT owner_id)::int AS distinct_request_owners
            FROM dz_first_party_chat_requests WHERE created_at >= now() - ($1::int * interval '1 day')""", days),
    )
    try:
        capabilities = await personal_status()
    except Exception:
        capabilities = None
    return {"days": days, "requests": requests, "daily": daily,
            "conversations": conversations, "workflows": workflows, "goals": goals,
            "memory": memory, "identity": identity_activity, "request_owners": owners, "capabilities": capabilities,
            "runtime": {"usage_ledger_ready": bool(ledger.available),
                        "parent_budget_ready": bool(parent_budget.active),
                        "agent_runtime_initialized": getattr(request.app.state, "agent_runtime", None) is not None,
                        "memory_storage_ready": bool(getattr(request.app.state, "personal_memory_ready", False)),
                        "mcp_manager_initialized": getattr(request.app.state, "mcp_connections", None) is not None}}


@app.api_route("/{prefix:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"])
async def inference(prefix: str, request: Request):
    path = "/" + prefix
    # Admin accounting is a distinct service-to-service scope; the inference
    # token must NEVER confer admin privileges.
    if path.startswith("/internal/agent/v1/media/"):
        if (caller_identity(request)!="agent-runtime" or
                os.getenv("DRAGONZPYDER_AGENT_MEDIA_ENABLED")!="1"):
            return denied(403,"Agent media capability unavailable")
        return await provider_request(request,path.removeprefix("/internal/agent/v1/media"),
                                      app_id="agent-media",runtime=runtime,agent_media=True)
    if path.startswith("/internal/provider/"):
        app_id = caller_identity(request)
        if app_id is None:
            return denied(401, "Service authentication required")
        return await provider_request(request, path.removeprefix("/internal/provider"),
                                      app_id=app_id, runtime=runtime)

    # Only the private agent runtime may inspect whether its actual GATEWAY
    # provider key has an immutable <=$0.50 cap. Never trust the lab's key.
    if path == "/internal/agent/v1/key-budget":
        if request.method != "GET":
            return denied(405, "Method not allowed")
        if (caller_identity(request) != "agent-runtime" or
                os.getenv("DRAGONZPYDER_AGENT_TOOL_CALLS_ENABLED") != "1"):
            return denied(403, "Agent runtime authentication required")
        if os.getenv("DRAGONZPYDER_AGENT_PAID_TEST_MAX_KEY_LIMIT_USD") != "0.50":
            return denied(503, "Paid staging budget guard is not enabled")
        from agent_platform.key_budget import verify_key_budget
        report = await verify_key_budget(
            request.app.state.http, os.getenv("OPENROUTER_API_KEY", "")
        )
        return JSONResponse(report)

    # Create parent USD budgets only through the authenticated
    # gateway. No client can create an unmetered parallel job from a browser.
    if path == "/internal/agent/v1/parallel-budget":
        if request.method != "POST":
            return denied(405, "POST required")
        if (caller_identity(request) != "agent-runtime" or
                os.getenv("DRAGONZPYDER_AGENT_TOOL_CALLS_ENABLED") != "1"):
            return denied(403, "Agent runtime authentication required")
        if not parent_budget.active:
            return denied(503, "Atomic parent budget gateway is disabled")
        try:
            raw = await request.body()
            if len(raw) > 512:
                return denied(413, "Budget request too large")
            item = json.loads(raw)
            if not isinstance(item, dict) or set(item) != {"job_id", "ceiling_usd"}:
                return denied(400, "Invalid budget request")
            from agent_platform.key_budget import verify_key_budget
            provider_cap = await verify_key_budget(
                request.app.state.http, os.getenv("OPENROUTER_API_KEY", "")
            )
            if provider_cap.get("approved") is not True:
                return denied(503, "Provider hard cap not verified")
            from decimal import Decimal
            if Decimal(str(item["ceiling_usd"])) > Decimal(
                    str(provider_cap["remaining_usd"])):
                return denied(429, "Approved provider allowance below parent ceiling")
            await parent_budget.create(job_id=item["job_id"],
                                       ceiling_usd=item["ceiling_usd"])
        except (ValueError, TypeError, KeyError, BudgetExceeded, json.JSONDecodeError):
            return denied(400, "Parent budget request rejected")
        except Exception:
            return denied(503, "Parent budget database unavailable")
        return JSONResponse({"status": "created", "job_id": item["job_id"],
                             "atomic_gateway_enforced": True})

    if path == "/internal/admin/config":
        if not admin_authorized(request):
            return denied(401, "Admin service authentication required")
        if request.method != "GET":
            return denied(405, "Method not allowed")
        return JSONResponse(admin_runtime_config(request), headers={"cache-control": "no-store"})

    if path == "/internal/admin/activity":
        if not admin_authorized(request):
            return denied(401, "Admin service authentication required")
        if request.method != "GET":
            return denied(405, "Method not allowed")
        raw_days = request.query_params.get("days", "30")
        if not raw_days.isdigit() or not 1 <= int(raw_days) <= 90:
            return denied(400, "Invalid days range")
        return JSONResponse(await admin_platform_activity(request, int(raw_days)),
                            headers={"cache-control": "no-store"})

    if path == "/internal/admin/usage":
        if not admin_authorized(request):
            return denied(401, "Admin service authentication required")
        if request.method != "GET":
            return denied(405, "Method not allowed")
        raw_days = request.query_params.get("days", "30")
        if not raw_days.isdigit() or not 1 <= int(raw_days) <= 90:
            return denied(400, "Invalid days range")
        app_id = request.query_params.get("app")
        if app_id and not re.fullmatch(r"[a-z0-9_-]{2,60}", app_id):
            return denied(400, "Invalid app name")
        summary = await ledger.summary(days=int(raw_days), app_id=app_id)
        return JSONResponse(summary) if summary else denied(503, "Usage ledger not configured")

    agent_protocol = path == "/internal/agent/v1/chat/completions"
    personal_protocol = path == "/internal/personal/v1/chat/completions"
    if not (agent_protocol or personal_protocol or path.startswith("/internal/v1/") or path.startswith("/v1/")):
        return JSONResponse({"error": {"message": "Unknown DragonZpyder API route"}}, status_code=404)
    if personal_protocol:
        # Dedicated service credential, distinct from Operly, legacy and agent
        # bearer credentials. No browser or user-supplied identity is accepted.
        bearer = request.headers.get("authorization", "")
        expected = os.getenv("DRAGONZPYDER_PERSONAL_BACKEND_TOKEN", "")
        if (os.getenv("DRAGONZPYDER_PERSONAL_GATEWAY_ENABLED") != "1"
                or len(expected) < 40):
            return denied(503, "Personal inference gateway disabled")
        if not (bearer.startswith("Bearer ") and
                hmac.compare_digest(bearer[7:], expected)):
            return denied(401, "Personal service authentication required")
        app_id = "personal-core"
    else:
        app_id = caller_identity(request)
        if app_id is None:
            return denied(401, "Service authentication required")
    if agent_protocol and (
        app_id != "agent-runtime" or
        os.getenv("DRAGONZPYDER_AGENT_TOOL_CALLS_ENABLED") != "1"
    ):
        return denied(403, "Agent gateway is disabled for this caller")
    route = "/v1/chat/completions" if (agent_protocol or personal_protocol) else path.removeprefix("/internal")
    if request.method == "GET" and route == "/v1/health":
        return {"service": "dragonzpyder-inference",
                "status": "ready" if os.getenv("OPENROUTER_API_KEY") else "unconfigured",
                "models": len(models()), "usage_ledger": ledger.available,
                 "paid_test_cap_guard": os.getenv("DRAGONZPYDER_STAGING_PAID_TEST_CAP_USD") == "0.50",
                 "atomic_parent_budget_ready": parent_budget.active}
    if request.method == "GET" and route == "/v1/models":
        return {"object": "list", "data": [{"id": model, "object": "model",
                                            "owned_by": "dragonzpyder"} for model in models()]}
    if request.method != "POST" or route != "/v1/chat/completions":
        return denied(405, "Unsupported inference endpoint")
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
        return denied(415, "JSON request required")
    if not os.getenv("OPENROUTER_API_KEY"):
        return denied(503, "Inference provider is not configured")
    if (agent_protocol or personal_protocol) and not ledger.available:
        return denied(503, "Metered inference requires persistent usage accounting")
    if not ledger.available and ledger.required:
        return denied(503, "Usage accounting unavailable")
    if not await runtime.enter():
        return JSONResponse({"error": {"message": "API is busy; retry shortly"}}, status_code=503,
                            headers={"retry-after": "2"})

    request_id = str(uuid4())
    started = time.monotonic()
    body = None
    provider_response = None
    served_model = None
    generation_id = None
    failure_code = None
    status = "error"
    response = None
    # Parent identities are supplied only by the already-authenticated
    # agent-runtime caller; reservations are made by this gateway.
    parent_job_id = request.headers.get("x-dragonzpyder-parent-job-id") if agent_protocol else None
    parent_reserved = False
    parent_finalized = False
    try:
        with inference_span(request, app_id, "unknown", request_id) as span:
            trace_id = span_trace_id(span) or request_id.replace("-", "")
            try:
                if request.headers.get("content-length", "0").isdigit() and int(request.headers.get("content-length", "0")) > MAX_BYTES:
                    raise GatewayError(413, "Request payload exceeds 160 KB")
                raw = await request.body()
                if len(raw) > MAX_BYTES:
                    raise GatewayError(413, "Request payload exceeds 160 KB")
                try:
                    decoded = json.loads(raw)
                    if agent_protocol:
                        try:
                            body = validate_agent_body(decoded, models())
                        except AgentProtocolError as error:
                            # Diagnostics contain only roles and value TYPES, never text.
                            safe_roles = {"system", "developer", "user", "assistant", "tool"}
                            shapes = [
                                ((item.get("role") if item.get("role") in safe_roles else "other"),
                                 type(item.get("content")).__name__)
                                for item in decoded.get("messages", [])[:20]
                                if isinstance(item, dict)
                            ] if isinstance(decoded, dict) and isinstance(decoded.get("messages"), list) else []
                            log.warning("Agent request shape rejection reason=%s shapes=%s", error.message, shapes)
                            raise GatewayError(error.status, error.message) from None
                    else:
                        body = valid_body(decoded)
                        if personal_protocol:
                            allowlist = {
                                x.strip() for x in os.getenv(
                                    "DRAGONZPYDER_PERSONAL_ALLOWED_MODELS", ""
                                ).split(",") if x.strip()
                            }
                            if not allowlist or body["model"] not in allowlist:
                                raise GatewayError(403, "Personal model not approved")
                            if body["max_tokens"] > 768:
                                raise GatewayError(400, "Personal output limit exceeded")
                            # Enforce provider-side ceilings too: catalog-based
                            # model selection alone cannot cap endpoint prices.
                            body["provider"] = {
                                "sort": "price",
                                "max_price": {"prompt": 0.25, "completion": 1.5},
                                "data_collection": "deny",
                            }
                            body["usage"] = {"include": True}
                except (ValueError, UnicodeDecodeError):
                    raise GatewayError(400, "Invalid JSON request")
                span.set_attribute("gen_ai.request.model", body["model"])
                span.set_attribute("gen_ai.request.max_tokens", body["max_tokens"])
                if agent_protocol and os.getenv("DRAGONZPYDER_AGENT_PAID_TEST_MAX_KEY_LIMIT_USD"):
                    if os.getenv("DRAGONZPYDER_AGENT_PAID_TEST_MAX_KEY_LIMIT_USD") != "0.50":
                        raise GatewayError(503, "Invalid staging paid-test budget guard")
                    from agent_platform.key_budget import verify_key_budget
                    budget = await verify_key_budget(
                        request.app.state.http, os.getenv("OPENROUTER_API_KEY", "")
                    )
                    if budget.get("approved") is not True:
                        log.warning("Agent paid-test preflight denied reason=%s", budget.get("reason"))
                        raise GatewayError(503, "Provider-enforced $0.50 key cap not verified")
                # Staging paid-agent calls are refused unless the *actual*
                # provider key proves an upstream-enforced cap <= $0.50.
                # The upstream provider enforces the aggregate cap even across
                # gateway replicas/retries; our ledger remains observational.
                if agent_protocol and os.getenv("RAILWAY_ENVIRONMENT_NAME") == "staging":
                    if os.getenv("DRAGONZPYDER_STAGING_PAID_TEST_CAP_USD") != "0.50":
                        raise GatewayError(503, "Staging model test budget guard not enabled")
                    try:
                        key_limit, remaining = await require_paid_test_cap(
                            request.app.state.http,
                            os.environ["OPENROUTER_API_KEY"],
                        )
                    except PaidTestBudgetError as error:
                        log.warning(
                            "Paid agent request denied: provider $0.50 cap unverified reason=%s",
                            str(error),
                        )
                        raise GatewayError(503, "Provider $0.50 spending cap not verified") from None
                    log.warning(
                        "Paid agent provider cap verified limit_usd=%s remaining_usd=%s",
                        key_limit, remaining,
                    )
                # Opt-in atomic global admission shared across Railway replicas.
                # Preserve the existing ceiling and do not silently fall back
                # to per-process counters when PostgreSQL is unavailable.
                if agent_protocol and os.getenv("DRAGONZPYDER_SHARED_AGENT_HOURLY_QUOTA") == "1":
                    hourly_limit = max(1, min(1000, int(os.getenv(
                        "DRAGONZPYDER_RUNTIME_CALLS_PER_HOUR", "120"
                    ))))
                    try:
                        admitted = await ledger.charge_agent_hour(hourly_limit)
                    except Exception:
                        raise GatewayError(503, "Shared inference quota unavailable") from None
                else:
                    admitted = await runtime.charge()
                if not admitted:
                    raise GatewayError(429, "DragonZpyder internal inference test quota reached")
                if parent_job_id is not None:
                    if not parent_budget.active:
                        raise GatewayError(503, "Parallel parent budget gateway is disabled")
                    # Recheck the same non-resetting provider hard cap on every
                    # paid parent dispatch, including production wakes.
                    from agent_platform.key_budget import verify_key_budget
                    cap = await verify_key_budget(request.app.state.http, os.getenv("OPENROUTER_API_KEY", ""))
                    if cap.get("approved") is not True:
                        raise GatewayError(503, "Provider hard cap not verified")
                    try:
                        await parent_budget.reserve(
                            job_id=parent_job_id, request_id=request_id,
                            payload_bytes=len(raw), output_tokens=body["max_tokens"]
                        )
                        parent_reserved = True
                    except (ValueError, BudgetExceeded):
                        raise GatewayError(429, "Atomic parent inference budget unavailable") from None
                    # Routing price ceilings match the conservative reservation
                    # bound. Do not override the provider's tool requirements.
                    body.setdefault("provider", {})["max_price"] = {
                        "prompt": 1.0, "completion": 4.0
                    }
                    body["usage"] = {"include": True}
                try:
                    # Only the agent protocol receives local admission pacing.
                    # One upstream request per attempt; never automatically
                    # retry ambiguous HTTP timeouts or network failures.
                    async with (agent_pacer.slot() if agent_protocol else nullcontext()):
                        upstream = await request.app.state.http.post(
                            OPENROUTER_URL, json=body,
                            headers={"authorization": "Bearer " + os.environ["OPENROUTER_API_KEY"],
                                     "HTTP-Referer": "https://dragonzpyder.xyz",
                                     "X-Title": "DragonZpyder Runtime",
                                     "X-DragonZpyder-Request-Id": request_id})
                except httpx.HTTPError:
                    raise GatewayError(502, "Inference service unavailable")
                if upstream.status_code != 200:
                    log.warning("Inference upstream returned status %s request_id=%s",
                                upstream.status_code, request_id)
                    code = 429 if upstream.status_code == 429 else 400 if upstream.status_code == 400 else 502
                    delay = (
                        await agent_pacer.cooldown(upstream.headers.get("retry-after"))
                        if code == 429 and agent_protocol else None
                    )
                    if code == 429 and parent_reserved:
                        try:
                            await parent_budget.settle_known_rejection(
                                job_id=parent_job_id, request_id=request_id)
                            parent_finalized = True
                        except Exception:
                            pass  # Any ambiguous release remains held.
                    raise GatewayError(
                        code, "Inference budget or rate limit reached" if code == 429
                              else "Model provider rejected the request",
                        retry_after=delay,
                    )
                try:
                    provider_response = upstream.json()
                    if agent_protocol:
                        payload = validate_agent_response(
                            provider_response, body["model"],
                            allowed_tool_names=(set() if body.get("tool_choice") == "none" else {
                                tool["function"]["name"] for tool in body.get("tools", [])
                            }),
                        )
                    else:
                        choice = provider_response["choices"][0]
                        answer = choice["message"]["content"]
                        if not isinstance(answer, str):
                            raise ValueError("nontext")
                        if len(answer.encode("utf-8")) > 90000:
                            raise GatewayError(502, "Model response exceeded output size limit")
                        payload = {"id": str(provider_response.get("id") or ""),
                                   "object": "chat.completion",
                                   "model": str(provider_response.get("model") or body["model"]),
                                   "choices": [{"index": 0, "message": {"role": "assistant", "content": answer},
                                                "finish_reason": choice.get("finish_reason") or "stop"}]}
                        if "usage" in provider_response:
                            payload["usage"] = provider_response["usage"]
                except (ValueError, TypeError, KeyError, IndexError, AgentProtocolError) as error:
                    if agent_protocol and os.getenv("DRAGONZPYDER_AGENT_SHAPE_DIAGNOSTICS") == "1":
                        # Shape metadata only. No raw output, reasoning tokens,
                        # message content, request, tool arguments or provider keys.
                        choice = (provider_response.get("choices") or [None])[0] if isinstance(
                            provider_response, dict
                        ) else None
                        message = choice.get("message") if isinstance(choice, dict) else None
                        message = message if isinstance(message, dict) else {}
                        tools = message.get("tool_calls")
                        output = message.get("content")
                        finish = choice.get("finish_reason") if isinstance(choice, dict) else None
                        finish = finish if finish in {"stop", "length", "tool_calls", "content_filter"} else "other"
                        detail = getattr(error, "message", type(error).__name__)
                        log.warning(
                            "Agent provider shape rejected reason=%s "
                            "finish=%s content_type=%s content_chars=%d "
                            "tools_type=%s tools_count=%d has_reasoning=%s request_id=%s",
                            detail, finish, type(output).__name__,
                            len(output) if isinstance(output, str) else 0,
                            type(tools).__name__,
                            len(tools) if isinstance(tools, list) else 0,
                            bool(message.get("reasoning") or message.get("reasoning_details")),
                            request_id,
                        )
                    # Only preserve a fixed, gateway-authored truncation label.
                    from agent_platform.gateway_protocol import OUTPUT_LIMIT_CODE, TOOL_SELECTION_CODE
                    if agent_protocol and isinstance(error, AgentProtocolError):
                        if error.code == OUTPUT_LIMIT_CODE:
                            raise GatewayError(502, "Model response stopped at output limit", code=OUTPUT_LIMIT_CODE) from None
                        if error.code == TOOL_SELECTION_CODE:
                            raise GatewayError(502, "Model tool selection rejected before dispatch", code=TOOL_SELECTION_CODE) from None
                    raise GatewayError(502, "Model provider returned unexpected content")
                served_model = str(provider_response.get("model") or body["model"])
                generation_id = str(provider_response.get("id") or "") or None
                if parent_reserved:
                    # Missing/invalid/above-bound provider usage never frees
                    # reserved dollars. The provider hard key cap still applies.
                    try:
                        await parent_budget.settle(job_id=parent_job_id,
                            request_id=request_id,
                            provider_response=provider_response)
                    finally:
                        parent_finalized = True
                response = JSONResponse(payload)
                status = "ok"
            except GatewayError as error:
                if parent_reserved and not parent_finalized:
                    try:
                        await parent_budget.settle(job_id=parent_job_id,
                            request_id=request_id, provider_response=None)
                    except Exception:
                        pass  # Hold is never automatically released.
                    parent_finalized = True
                failure_code = str(error.status)
                if agent_protocol:
                    # Only authored validation labels; never record prompts or schemas.
                    log.warning("Agent gateway request rejected status=%s reason=%s request_id=%s",
                                error.status, error.message, request_id)
                response = denied(error.status, error.message, code=error.code)
                if error.retry_after is not None:
                    response.headers["retry-after"] = str(error.retry_after)
            except Exception as error:
                if parent_reserved and not parent_finalized:
                    try:
                        await parent_budget.settle(job_id=parent_job_id,
                            request_id=request_id, provider_response=None)
                    except Exception:
                        pass
                    parent_finalized = True
                log.exception("Unexpected inference exception request_id=%s type=%s", request_id, type(error).__name__)
                failure_code = "502"
                response = denied(502, "Inference service unavailable")

            duration_ms = max(0, int((time.monotonic() - started) * 1000))
            span.set_attribute("dragonzpyder.status", status)
            span.set_attribute("dragonzpyder.latency_ms", duration_ms)
            if served_model:
                span.set_attribute("gen_ai.response.model", served_model)
            usage = token_usage(provider_response)
            for key, attribute in (("input_tokens", "gen_ai.usage.input_tokens"),
                                   ("output_tokens", "gen_ai.usage.output_tokens"),
                                   ("total_tokens", "dragonzpyder.usage.total_tokens")):
                if usage[key] is not None:
                    span.set_attribute(attribute, usage[key])
            if failure_code:
                span.set_attribute("dragonzpyder.failure_code", failure_code)
            try:
                persisted = await ledger.record(
                    request_id=request_id, app_id=app_id, trace_id=trace_id,
                    requested_model=body["model"] if body else "invalid",
                    served_model=served_model, generation_id=generation_id,
                    status=status, duration_ms=duration_ms, response=provider_response,
                    request_payload=body, failure_code=failure_code)
            except Exception:
                persisted = False
            if not persisted and ledger.required:
                response = denied(503, "Inference accounting failed; response withheld")
                span.set_attribute("dragonzpyder.accounting_failed", True)
            response.headers["x-dragonzpyder-trace-id"] = trace_id
            response.headers["x-dragonzpyder-request-id"] = request_id
            response.headers["x-dragonzpyder-audit"] = "persisted" if persisted else "unavailable"
            return response
    finally:
        await runtime.leave()
