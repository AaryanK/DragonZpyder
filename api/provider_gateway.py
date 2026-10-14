"""Scoped OpenRouter transport for DragonZpyder first-party applications.

The gateway owns OpenRouter credentials. Image-generation requests use a
separate, capped test key and fail closed when it is absent; no images ever
fall back to the ordinary inference key. AI Mesh retains its session, model,
confirmation and daily-limit checks. The gateway enforces an operation
allowlist, caller identity, bounds, tracing and usage accounting.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from uuid import uuid4

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from opentelemetry import trace
from opentelemetry.propagate import extract
from opentelemetry.trace import Status, StatusCode

from usage_ledger import ledger, token_usage

log = logging.getLogger(__name__)
OPENROUTER = "https://openrouter.ai/api/v1"
PAID_PATHS = {"/chat/completions", "/images", "/audio/transcriptions", "/audio/speech", "/videos"}
CATALOG_PATHS = {"/models", "/images/models", "/videos/models"}
VIDEO_PATH = re.compile(r"^/videos/[-\w]{1,150}(?:/content)?$")
MAX_PAYLOAD = 12 * 1024 * 1024
MAX_RESULT = 16 * 1024 * 1024


def error_response(code, message):
    return JSONResponse({"error": {"message": message, "code": code}}, status_code=code)


def _provider_key(path):
    # Image models and generation MUST use the capped test key, never the
    # unrestricted key shared by other apps. Fail closed while unconfigured.
    if path in ("/images/models", "/images"):
        return os.getenv("DRAGONZPYDER_IMAGE_OPENROUTER_API_KEY", "")
    return os.getenv("OPENROUTER_API_KEY", "")


def _operation(method: str, path: str) -> str | None:
    if method == "GET" and (path in CATALOG_PATHS or VIDEO_PATH.fullmatch(path)):
        return "lookup"
    if method == "POST" and path in PAID_PATHS:
        return "generation"
    return None


def _json_payload(raw: bytes, path: str):
    try:
        body = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise ValueError("JSON request required")
    if not isinstance(body, dict):
        raise ValueError("Request body must be a JSON object")
    model = body.get("model")
    if not isinstance(model, str) or not re.fullmatch(r"[a-zA-Z0-9_.:/-]{3,120}", model):
        raise ValueError("Missing or invalid model")
    if path == "/chat/completions":
        messages = body.get("messages")
        if not isinstance(messages, list) or not 1 <= len(messages) <= 30:
            raise ValueError("Invalid conversation")
        if any(not isinstance(m, dict) or m.get("role") not in
               ("system", "developer", "user", "assistant", "tool") for m in messages):
            raise ValueError("Invalid message role")
        limit = body.get("max_tokens", 1024)
        if type(limit) is not int or not 1 <= limit <= 4096:
            raise ValueError("Invalid output token limit")
        if body.get("tools") or body.get("tool_choice"):
            raise ValueError("Tool calling is unavailable in AI Mesh")
        if body.get("stream") is True:
            # Ask OpenRouter for the final usage frame while streaming.
            body["stream_options"] = {"include_usage": True}
        elif body.get("stream") not in (False, None):
            raise ValueError("Invalid streaming option")
    else:
        if body.get("stream"):
            raise ValueError("Streaming is supported for chat completions only")
    if path == "/images":
        prompt = body.get("prompt")
        if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 1600:
            raise ValueError("Invalid image prompt")
        # Enforce the one-image smoke-test contract at the central gateway too.
        if type(body.get("n", 1)) is not int or body.get("n", 1) != 1:
            raise ValueError("Only one image per request is permitted")
        body["n"] = 1
    return body


def _metadata(response, binary: bool = False):
    if binary:
        return {"media_bytes": len(response.content),
                "media_sha256": hashlib.sha256(response.content).hexdigest(),
                "content_type": response.headers.get("content-type", "application/octet-stream")}
    try:
        result = response.json()
        return result if isinstance(result, dict) else {"result_type": "non_object"}
    except ValueError:
        return {"unparseable_response": True, "media_sha256": hashlib.sha256(response.content).hexdigest()}


def _start_span(request, app_id, path, request_id, model):
    tracer = trace.get_tracer("dragonzpyder.provider.gateway", "1.0")
    span = tracer.start_span("openrouter." + path.strip("/").replace("/", "."),
                             context=extract(dict(request.headers)))
    span.set_attribute("gen_ai.system", "openrouter")
    span.set_attribute("gen_ai.operation.name", path.strip("/"))
    span.set_attribute("gen_ai.request.model", model)
    span.set_attribute("dragonzpyder.app_id", app_id)
    span.set_attribute("dragonzpyder.request_id", request_id)
    context = span.get_span_context()
    trace_id = f"{context.trace_id:032x}" if context.is_valid else request_id.replace("-", "")
    return span, trace_id


def _finish_span(span, result, code, duration_ms):
    span.set_attribute("http.response.status_code", code)
    span.set_attribute("dragonzpyder.latency_ms", duration_ms)
    if code >= 400:
        span.set_status(Status(StatusCode.ERROR))
    if isinstance(result, dict):
        model = result.get("model")
        if isinstance(model, str):
            span.set_attribute("gen_ai.response.model", model)
        usage = token_usage(result)
        for key, attr in (("input_tokens", "gen_ai.usage.input_tokens"),
                          ("output_tokens", "gen_ai.usage.output_tokens"),
                          ("total_tokens", "dragonzpyder.usage.total_tokens")):
            if usage[key] is not None:
                span.set_attribute(attr, usage[key])
    span.end()


async def provider_request(request: Request, path: str, *, app_id: str, runtime):
    """Called only after the central gateway validates the app-specific key."""
    op = _operation(request.method, path)
    if op is None:
        return error_response(404, "Unsupported provider route")
    if not (app_id == "ai-mesh" or (app_id in {"chat-lab", "operly"} and path == "/chat/completions" and request.method == "POST")):
        return error_response(403, "This provider operation is not enabled for the application")
    provider_key = _provider_key(path)
    if not provider_key:
        return error_response(503, "Image test provider is not configured" if
                              path in ("/images", "/images/models") else
                              "Inference provider is not configured")
    if op == "generation" and ledger.required and not ledger.available:
        return error_response(503, "Usage accounting unavailable")
    if not await runtime.enter():
        return error_response(503, "Inference capacity reached")
    release = True
    request_id = str(uuid4())
    started = time.monotonic()
    try:
        payload = None
        is_stream = False
        if op == "generation":
            if not await runtime.charge():
                return error_response(429, "Inference rate limit reached")
            if request.headers.get("content-type", "").split(";", 1)[0].lower().strip() != "application/json":
                return error_response(415, "JSON request required")
            raw = await request.body()
            if len(raw) > MAX_PAYLOAD:
                return error_response(413, "Request too large")
            try:
                payload = _json_payload(raw, path)
            except ValueError as exc:
                return error_response(400, str(exc))
            is_stream = payload.get("stream") is True
        model = str((payload or {}).get("model") or "catalog")
        span, trace_id = _start_span(request, app_id, path, request_id, model)
        headers = {"authorization": "Bearer " + provider_key,
                   "HTTP-Referer": "https://dragonzpyder.xyz",
                   "X-Title": "DragonZpyder Gateway",
                   "X-DragonZpyder-Request-Id": request_id}
        if payload is not None:
            headers["content-type"] = "application/json"
        query = {"index": "0"} if path.endswith("/content") else None
        if is_stream:
            try:
                upstream = await request.app.state.http.send(
                    request.app.state.http.build_request(
                        "POST", OPENROUTER + path,
                        json=payload, headers=headers, timeout=120),
                    stream=True)
            except httpx.HTTPError:
                _finish_span(span, None, 502, int((time.monotonic()-started)*1000))
                return error_response(502, "Model streaming unavailable")
            if upstream.status_code != 200:
                code = 429 if upstream.status_code == 429 else 502
                await upstream.aclose()
                _finish_span(span, None, code, int((time.monotonic()-started)*1000))
                return error_response(code, "Model provider rejected the request")
            release = False
            async def relay():
                buffer = b""
                usage = None
                chunks = []
                content_bytes = 0
                generation_id = None
                served_model = None
                completed = False
                failed = None
                try:
                    # MockTransport and some middleware pre-consume responses;
                    # ordinary OpenRouter SSE remains a true byte stream.
                    async def source_blocks():
                        if upstream.is_stream_consumed:
                            yield upstream.content
                        else:
                            async for piece in upstream.aiter_raw():
                                yield piece
                    async for block in source_blocks():
                        buffer += block
                        while b"\n" in buffer:
                            line, buffer = buffer.split(b"\n", 1)
                            if line.startswith(b"data:"):
                                value = line[5:].strip()
                                if value == b"[DONE]":
                                    completed = True
                                else:
                                    try:
                                        event = json.loads(value)
                                    except (ValueError, UnicodeDecodeError):
                                        event = None
                                    if isinstance(event, dict):
                                        if isinstance(event.get("usage"), dict):
                                            usage = event["usage"]
                                        if event.get("error"):
                                            failed = "stream_error"
                                        if isinstance(event.get("id"), str):
                                            generation_id = event["id"]
                                        if isinstance(event.get("model"), str):
                                            served_model = event["model"]
                                        delta = ((event.get("choices") or [{}])[0].get("delta") or {}).get("content") if event.get("choices") else None
                                        if isinstance(delta, str):
                                            size = len(delta.encode("utf-8"))
                                            content_bytes += size
                                            if content_bytes <= MAX_RESULT and ledger.encryption_key:
                                                chunks.append(delta)
                        yield block
                    if not completed and failed is None:
                        failed = "stream_interrupted"
                except (httpx.HTTPError, OSError):
                    failed = "stream_interrupted"
                    raise
                finally:
                    await upstream.aclose()
                    report = {"id": generation_id, "model": served_model or model,
                              "usage": usage} if usage is not None else {
                                  "id": generation_id, "model": served_model or model}
                    if ledger.encryption_key and chunks:
                        report["streamed_content"] = "".join(chunks)
                        if content_bytes > MAX_RESULT:
                            report["streamed_content_truncated"] = True
                    elapsed = int((time.monotonic()-started)*1000)
                    code = 200 if completed and not failed else 502
                    try:
                        if op == "generation":
                            await ledger.record(
                                request_id=request_id, app_id=app_id, trace_id=trace_id,
                                requested_model=model, served_model=served_model,
                                generation_id=generation_id, status="ok" if code == 200 else "error",
                                duration_ms=elapsed, response=report, request_payload=payload,
                                failure_code=failed)
                    except Exception:
                        log.exception("Streaming usage persistence failed %s", request_id)
                    _finish_span(span, report, code, elapsed)
                    await runtime.leave()
            return StreamingResponse(relay(), media_type="text/event-stream",
                 headers={"cache-control": "no-store, no-transform",
                          "x-accel-buffering": "no", "x-dragonzpyder-request-id": request_id,
                          "x-dragonzpyder-trace-id": trace_id})
        try:
            upstream = await request.app.state.http.request(
                request.method, OPENROUTER + path, headers=headers,
                json=payload, params=query, timeout=120)
        except httpx.HTTPError:
            _finish_span(span, None, 502, int((time.monotonic()-started)*1000))
            return error_response(502, "Model provider unavailable")
        if len(upstream.content) > MAX_RESULT:
            _finish_span(span, None, 502, int((time.monotonic()-started)*1000))
            return error_response(502, "Provider response size exceeded")
        is_binary = path.endswith("/content") or path == "/audio/speech"
        report = _metadata(upstream, binary=is_binary)
        elapsed = int((time.monotonic()-started)*1000)
        status_code = upstream.status_code
        recorded = True
        if op == "generation":
            try:
                recorded = await ledger.record(
                    request_id=request_id, app_id=app_id, trace_id=trace_id,
                    requested_model=model,
                    served_model=report.get("model") if isinstance(report.get("model"), str) else model,
                    generation_id=str(report.get("id") or "") or None,
                    status="ok" if 200 <= status_code < 300 else "error",
                    duration_ms=elapsed, response=report, request_payload=payload,
                    failure_code=None if 200 <= status_code < 300 else str(status_code))
            except Exception:
                recorded = False
        _finish_span(span, report, status_code, elapsed)
        if op == "generation" and ledger.required and not recorded:
            return error_response(503, "Inference accounting unavailable")
        # Do not expose raw upstream provider errors or headers to the browser.
        if not 200 <= status_code < 300:
            return error_response(429 if status_code == 429 else 502, "Provider request failed")
        media = upstream.headers.get("content-type", "application/json")
        if is_binary and not (media.startswith("audio/") or media.startswith("video/")):
            return error_response(502, "Unexpected provider media type")
        return Response(content=upstream.content, status_code=status_code,
                        media_type=media.split(";", 1)[0],
                        headers={"cache-control": "no-store",
                                 "x-dragonzpyder-request-id": request_id,
                                 "x-dragonzpyder-trace-id": trace_id,
                                 "x-dragonzpyder-audit": "persisted" if recorded else "unavailable"})
    finally:
        if release:
            await runtime.leave()
