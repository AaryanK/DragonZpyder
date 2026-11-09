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
from agent_platform.workflows.router import router as workflow_router
from agent_platform.goal_router import router as goals_router
from agent_platform.openrouter_spend_guard import PaidTestBudgetError, require_paid_test_cap
from agent_platform.provider_pacing import AgentProviderPacer
from agent_platform.gateway_parent_budget import ParentBudgetGateway
from agent_platform.budget_reservations import BudgetExceeded

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_BYTES = 160_000
MODEL_PATTERN = re.compile(r"^[a-zA-Z0-9_.:/-]{3,100}$")


class GatewayError(Exception):
    def __init__(self, status: int, message: str, *, retry_after: int | None = None):
        self.status = status
        self.message = message
        self.retry_after = retry_after


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
    log.warning("Staging atomic parent-budget gateway status=%s",
                "ready" if parent_budget.active else "disabled")
    agent_runtime = None
    goal_pool = None
    try:
        if os.getenv("DRAGONZPYDER_GOAL_STORE_ENABLED") == "1":
            # The schema must be migrated separately. Do not silently create
            # tables or start user work from an API process.
            import asyncpg
            from agent_platform.goal_store import DurableGoalStore
            goal_dsn = os.getenv("DRAGONZPYDER_GOALS_DATABASE_URL", "")
            if not goal_dsn.startswith(("postgres://", "postgresql://")):
                raise RuntimeError("Dedicated persistent goals database is not configured")
            goal_pool = await asyncpg.create_pool(dsn=goal_dsn, min_size=1, max_size=4)
            async with goal_pool.acquire() as con:
                for required_table in ("dragonzpyder_goals", "dragonzpyder_goal_runs"):
                    if await con.fetchval("SELECT to_regclass($1)", required_table) is None:
                        raise RuntimeError("DragonZpyder goal schema migration is incomplete")
            app.state.goal_store = DurableGoalStore(
                goal_pool, encryption_key=os.getenv("DRAGONZPYDER_GOALS_ENCRYPTION_KEY", ""),
            )
        if os.getenv("DRAGONZPYDER_AGENTS_ENABLED") == "1":
            from agent_platform.runtime import AgentRuntime
            agent_runtime = AgentRuntime()
            await agent_runtime.start()
            app.state.agent_runtime = agent_runtime
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
            yield
    finally:
        if agent_runtime is not None:
            await agent_runtime.close()
        if goal_pool is not None:
            await goal_pool.close()
        await parent_budget.close()
        await ledger.close()
        shutdown_telemetry()


app = FastAPI(title="DragonZpyder API", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
app.include_router(agent_router)
app.include_router(workflow_router)
app.include_router(goals_router)


@app.middleware("http")
async def headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["x-content-type-options"] = "nosniff"
    response.headers["referrer-policy"] = "no-referrer"
    response.headers["cache-control"] = "no-store"
    # Do not grant credentialed browser CORS to the private inference API.
    response.headers["access-control-allow-origin"] = "null"
    return response


def denied(status: int, message: str) -> JSONResponse:
    return JSONResponse({"error": {"message": message, "type": "dragonzpyder_inference_error", "code": status}}, status_code=status)


def models() -> list[str]:
    raw = os.getenv("DRAGONZPYDER_RUNTIME_ALLOWED_MODELS", "openai/gpt-oss-120b")
    return list(dict.fromkeys(x for item in raw.split(",") if (x := item.strip()) and MODEL_PATTERN.fullmatch(x)))[:20]


def caller_identity(request: Request) -> str | None:
    """Derive the app ID from an operator-issued secret, never a browser header."""
    header = request.headers.get("authorization", "")
    if not header.startswith("Bearer "):
        return None
    bearer = header[7:]
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


@app.api_route("/{prefix:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"])
async def inference(prefix: str, request: Request):
    path = "/" + prefix
    # Admin accounting is a distinct service-to-service scope; the inference
    # token must NEVER confer admin privileges.
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

    # Create parent USD budgets only through the authenticated staging
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
                if not await runtime.charge():
                    raise GatewayError(429, "DragonZpyder internal inference test quota reached")
                if parent_job_id is not None:
                    if not parent_budget.active:
                        raise GatewayError(503, "Parallel parent budget gateway is disabled")
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
                            allowed_tool_names={
                                tool["function"]["name"] for tool in body.get("tools", [])
                            },
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
                response = denied(error.status, error.message)
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
