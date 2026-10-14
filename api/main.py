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
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from observability import setup_telemetry, shutdown_telemetry, inference_span, span_trace_id
from usage_ledger import ledger, token_usage

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_BYTES = 160_000
MODEL_PATTERN = re.compile(r"^[a-zA-Z0-9_.:/-]{3,100}$")


class GatewayError(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message


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
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_telemetry()
    await ledger.open()
    try:
        async with httpx.AsyncClient(timeout=90.0, follow_redirects=False) as client:
            app.state.http = client
            yield
    finally:
        await ledger.close()
        shutdown_telemetry()


app = FastAPI(title="DragonZpyder API", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)


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

    if not (path.startswith("/internal/v1/") or path.startswith("/v1/")):
        return JSONResponse({"error": {"message": "Unknown DragonZpyder API route"}}, status_code=404)
    app_id = caller_identity(request)
    if app_id is None:
        return denied(401, "Service authentication required")
    route = path.removeprefix("/internal")
    if request.method == "GET" and route == "/v1/health":
        return {"service": "dragonzpyder-inference",
                "status": "ready" if os.getenv("OPENROUTER_API_KEY") else "unconfigured",
                "models": len(models()), "usage_ledger": ledger.available}
    if request.method == "GET" and route == "/v1/models":
        return {"object": "list", "data": [{"id": model, "object": "model",
                                            "owned_by": "dragonzpyder"} for model in models()]}
    if request.method != "POST" or route != "/v1/chat/completions":
        return denied(405, "Unsupported inference endpoint")
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
        return denied(415, "JSON request required")
    if not os.getenv("OPENROUTER_API_KEY"):
        return denied(503, "Inference provider is not configured")
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
                    body = valid_body(json.loads(raw))
                except (ValueError, UnicodeDecodeError):
                    raise GatewayError(400, "Invalid JSON request")
                span.set_attribute("gen_ai.request.model", body["model"])
                span.set_attribute("gen_ai.request.max_tokens", body["max_tokens"])
                if not await runtime.charge():
                    raise GatewayError(429, "DragonZpyder internal inference test quota reached")
                try:
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
                    raise GatewayError(code, "Inference budget or rate limit reached" if code == 429
                                       else "Model provider rejected the request")
                try:
                    provider_response = upstream.json()
                    choice = provider_response["choices"][0]
                    answer = choice["message"]["content"]
                    if not isinstance(answer, str):
                        raise ValueError("nontext")
                    if len(answer.encode("utf-8")) > 90000:
                        raise GatewayError(502, "Model response exceeded output size limit")
                except (ValueError, TypeError, KeyError, IndexError):
                    raise GatewayError(502, "Model provider returned unexpected content")
                served_model = str(provider_response.get("model") or body["model"])
                generation_id = str(provider_response.get("id") or "") or None
                payload = {"id": generation_id or "", "object": "chat.completion",
                           "model": served_model,
                           "choices": [{"index": 0, "message": {"role": "assistant", "content": answer},
                                        "finish_reason": choice.get("finish_reason") or "stop"}]}
                if "usage" in provider_response:
                    payload["usage"] = provider_response["usage"]
                response = JSONResponse(payload)
                status = "ok"
            except GatewayError as error:
                failure_code = str(error.status)
                response = denied(error.status, error.message)
            except Exception as error:
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
