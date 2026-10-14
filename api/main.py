"""DragonZpyder's private, OpenAI-compatible model gateway (FastAPI).

The gateway authenticates backend callers; Operly remains responsible for
organisation, workspace, and user permissions. It never trusts browser cookies.
"""
import asyncio
import hmac
import math
import os
import re
import time
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with httpx.AsyncClient(timeout=90.0, follow_redirects=False) as client:
        app.state.http = client
        yield


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


def authorized(request: Request) -> bool:
    secret = os.getenv("DRAGONZPYDER_RUNTIME_TOKEN", "")
    header = request.headers.get("authorization", "")
    return (len(secret) >= 32 and header.startswith("Bearer ") and
            hmac.compare_digest(header[7:].encode(), secret.encode()))


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
    if not (path.startswith("/internal/v1/") or path.startswith("/v1/")):
        return JSONResponse({"error": {"message": "Unknown DragonZpyder API route"}}, status_code=404)
    if not authorized(request):
        return denied(401, "Service authentication required")
    route = path.removeprefix("/internal")
    if request.method == "GET" and route == "/v1/health":
        return {"service": "dragonzpyder-inference", "status": "ready" if os.getenv("OPENROUTER_API_KEY") else "unconfigured",
                "models": len(models())}
    if request.method == "GET" and route == "/v1/models":
        return {"object": "list", "data": [{"id": model, "object": "model", "owned_by": "dragonzpyder"} for model in models()]}
    if request.method != "POST" or route != "/v1/chat/completions":
        return denied(405, "Unsupported inference endpoint")
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
        return denied(415, "JSON request required")
    if not os.getenv("OPENROUTER_API_KEY"):
        return denied(503, "Inference provider is not configured")
    if not await runtime.enter():
        return JSONResponse({"error": {"message": "API is busy; retry shortly"}}, status_code=503,
                            headers={"retry-after": "2"})
    try:
        if request.headers.get("content-length", "0").isdigit() and int(request.headers.get("content-length", "0")) > MAX_BYTES:
            raise GatewayError(413, "Request payload exceeds 160 KB")
        raw = await request.body()
        if len(raw) > MAX_BYTES:
            raise GatewayError(413, "Request payload exceeds 160 KB")
        try:
            import json
            body = valid_body(json.loads(raw))
        except (ValueError, UnicodeDecodeError):
            raise GatewayError(400, "Invalid JSON request")
        if not await runtime.charge():
            raise GatewayError(429, "DragonZpyder internal inference test quota reached")
        try:
            upstream = await request.app.state.http.post(
                OPENROUTER_URL, json=body,
                headers={"authorization": "Bearer " + os.environ["OPENROUTER_API_KEY"],
                         "HTTP-Referer": "https://dragonzpyder.xyz", "X-Title": "DragonZpyder Runtime"})
        except httpx.HTTPError:
            raise GatewayError(502, "Inference service unavailable")
        if upstream.status_code != 200:
            print("DragonZpyder inference upstream status", upstream.status_code)
            status = 429 if upstream.status_code == 429 else 400 if upstream.status_code == 400 else 502
            raise GatewayError(status, "Inference budget or rate limit reached" if status == 429
                               else "Model provider rejected the request")
        try:
            result = upstream.json()
            choice = result["choices"][0]
            answer = choice["message"]["content"]
            if not isinstance(answer, str):
                raise ValueError("nontext")
            if len(answer.encode("utf-8")) > 90000:
                raise GatewayError(502, "Model response exceeded output size limit")
        except (ValueError, TypeError, KeyError, IndexError):
            raise GatewayError(502, "Model provider returned unexpected content")
        payload = {"id": str(result.get("id", "")), "object": "chat.completion",
                   "model": str(result.get("model") or body["model"]),
                   "choices": [{"index": 0, "message": {"role": "assistant", "content": answer},
                                "finish_reason": choice.get("finish_reason") or "stop"}]}
        if "usage" in result:
            payload["usage"] = result["usage"]
        return JSONResponse(payload)
    except GatewayError as error:
        return denied(error.status, error.message)
    except Exception as error:
        print("DragonZpyder inference unexpected error", type(error).__name__)
        return denied(502, "Inference service unavailable")
    finally:
        await runtime.leave()
