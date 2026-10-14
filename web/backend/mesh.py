"""Python AI Mesh with Personal-only sessions and bounded provider access.

Ports the current Node Mesh's endpoint contracts. Quotas are per-process test
limits, NOT financial controls. Image/video remain off unless explicitly enabled.
"""
import asyncio
import base64
import binascii
from io import BytesIO
from zipfile import ZipFile, BadZipFile
from docx import Document
import hashlib
import hmac
import json
import math
import os
import re
import time
from collections import defaultdict
from datetime import datetime, timezone
from urllib.parse import quote

import httpx
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from .security import personal_session

# The Mesh service never talks to OpenRouter directly; only the central gateway does.
BASE = os.getenv("DRAGONZPYDER_API_ORIGIN", "http://dragonzpyder-api.railway.internal:8080").rstrip("/") + "/internal/provider"
_cache = {}
_counts = defaultdict(int)
_count_lock = asyncio.Lock()
DATA_PATTERN = re.compile(r"^data:([\w.+/-]+);base64,([A-Za-z0-9+/=]+)$")
VIDEO_ID = re.compile(r"^[-\w]{1,150}$")
FORMATS = {"audio/webm": "webm", "audio/mpeg": "mp3", "audio/mp4": "m4a",
           "audio/ogg": "ogg", "audio/wav": "wav", "audio/flac": "flac"}
MAX_BODY = 12 * 1024 * 1024
MAX_FILE_BYTES = 3 * 1024 * 1024
MAX_ALL_FILES = 7 * 1024 * 1024
SYSTEM = (
    "You are DragonZpyder AI Mesh. Give useful, precise answers. You may "
    "analyse supplied text and images. You have no access to connected "
    "accounts or tools; users should switch to Agent for external actions."
)


def fail(code, message):
    raise HTTPException(status_code=code, detail={"message": message})


def provider_headers():
    secret = os.getenv("DRAGONZPYDER_MESH_GATEWAY_TOKEN")
    if not secret or len(secret) < 32:
        fail(503, "DragonZpyder inference gateway is not configured")
    return {"authorization": "Bearer " + secret, "content-type": "application/json"}


async def upstream(client, path, method="GET", data=None, timeout=60):
    try:
        response = await client.request(method, BASE + path, headers=provider_headers(),
                                        json=data, timeout=timeout)
    except httpx.HTTPError:
        fail(502, "AI provider unavailable")
    if not response.is_success:
        # Do not reflect arbitrary upstream content, which could expose internal details.
        fail(502 if response.status_code >= 500 else response.status_code,
             "AI provider request failed")
    return response


async def catalogue(client, kind):
    entry = _cache.get(kind)
    if entry and entry[0] > time.monotonic():
        return entry[1]
    path = {"chat": "/models", "image": "/images/models", "video": "/videos/models"}[kind]
    result = await upstream(client, path, timeout=14)
    data = result.json().get("data", [])
    models = data if isinstance(data, list) else []
    _cache[kind] = (time.monotonic() + 900, models)
    return models


def modalities(model, direction):
    value = (model.get("architecture") or {}).get(direction + "_modalities") or []
    return value if isinstance(value, list) else []


def cost(model):
    try:
        value = float((model.get("pricing") or {}).get("prompt")) + float(
            (model.get("pricing") or {}).get("completion"))
        return value if math.isfinite(value) and value >= 0 else float("inf")
    except (TypeError, ValueError):
        return float("inf")


def brief(model):
    return {"id": model.get("id"), "name": model.get("name") or model.get("id")}


async def model_list(client):
    chat = await catalogue(client, "chat")
    async def optional(kind):
        try:
            return await catalogue(client, kind)
        except Exception:
            return []
    images, videos = await asyncio.gather(optional("image"), optional("video"))
    chats = sorted((m for m in chat if "text" in modalities(m, "input")
                    and "text" in modalities(m, "output")), key=cost)[:500]
    return {
        "chat": [{**brief(m), "inputs": modalities(m, "input"), "outputs": modalities(m, "output"),
                  "promptPrice": (m.get("pricing") or {}).get("prompt"),
                  "completionPrice": (m.get("pricing") or {}).get("completion"),
                  "context": m.get("context_length")} for m in chats],
        "image": [brief(m) for m in images[:80]],
        "video": [{**brief(m), "options": {
            "durations": m.get("supported_durations") or [],
            "resolutions": m.get("supported_resolutions") or [],
            "ratios": m.get("supported_aspect_ratios") or [],
            "pricing": m.get("pricing_skus") or {}}} for m in videos[:80]],
        "tts": [brief(m) for m in chat if "speech" in modalities(m, "output")][:40],
        "stt": [brief(m) for m in chat if "transcription" in modalities(m, "output")][:40],
        "imageEnabled": os.getenv("MESH_ENABLE_IMAGE") == "true",
        "videoEnabled": os.getenv("MESH_ENABLE_VIDEO") == "true",
    }


async def take(identity, kind):
    limit = {"chat": 40, "image": 2, "video": 1, "speech": 10, "transcribe": 10}[kind]
    day = datetime.now(timezone.utc).date().isoformat()
    key = (day, identity, kind)
    async with _count_lock:
        for old in list(_counts):
            if old[0] != day:
                del _counts[old]
        if _counts[key] >= limit:
            fail(429, "Daily AI Mesh test limit reached for " + kind)
        _counts[key] += 1


def choose(models, model_id):
    return next((m for m in models if m.get("id") == model_id), None)


def parse_attachment(raw, allowed):
    if not isinstance(raw, str) or len(raw) > 5 * 1024 * 1024:
        fail(400, "Unsupported attachment or too large (3.5 MB maximum)")
    match = DATA_PATTERN.fullmatch(raw)
    if not match or match.group(1) not in allowed:
        fail(400, "Unsupported attachment or too large (3.5 MB maximum)")
    return {"value": raw, "mime": match.group(1), "data": match.group(2)}


def document_part(part):
    """Convert tightly bounded user files to OpenRouter PDF or plain-text parts."""
    entry = part.get("file")
    if not isinstance(entry, dict):
        fail(400, "Invalid file attachment")
    filename = entry.get("filename")
    source = entry.get("file_data")
    if not isinstance(filename, str) or not 1 <= len(filename) <= 120:
        fail(400, "Invalid attachment filename")
    name = filename.replace(chr(92), "/").rsplit("/", 1)[-1]
    extension = os.path.splitext(name)[-1].lower()
    if not isinstance(source, str) or len(source) > 4_400_000:
        fail(413, "Attachment exceeds 3 MB")
    match = DATA_PATTERN.fullmatch(source)
    if not match:
        fail(400, "Attachment must be base64 encoded")
    mime = match.group(1)
    try:
        data = base64.b64decode(match.group(2), validate=True)
    except (binascii.Error, ValueError):
        fail(400, "Invalid file encoding")
    if not data or len(data) > MAX_FILE_BYTES:
        fail(413, "Attachment exceeds 3 MB")
    if extension == ".pdf" and mime == "application/pdf":
        if not data.startswith(b"%PDF-"):
            fail(400, "Invalid PDF attachment")
        return {"type": "file", "file": {"filename": name, "file_data": source}}, len(data), True
    if extension == ".docx" and mime in (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/octet-stream"):
        if len(data) > 1_000_000:
            fail(413, "DOCX must be smaller than 1 MB")
        try:
            with ZipFile(BytesIO(data)) as archive:
                if sum(info.file_size for info in archive.infolist()) > 5_000_000:
                    fail(413, "DOCX expands beyond allowed size")
            doc = Document(BytesIO(data))
            content = "\n".join(p.text for p in doc.paragraphs)
            for table in doc.tables:
                for row in table.rows:
                    content += "\n" + " | ".join(cell.text for cell in row.cells)
        except (BadZipFile, ValueError, KeyError, OSError):
            fail(400, "Invalid DOCX attachment")
        return {"type": "text", "text": f"Attached document ({name}):\n{content[:8000]}"}, len(data), False
    if extension in (".txt", ".md", ".csv", ".json", ".py", ".log") and mime in (
            "text/plain", "text/markdown", "text/csv", "application/json", "text/x-python",
            "application/octet-stream"):
        if len(data) > 250_000:
            fail(413, "Text file exceeds 250 KB")
        try:
            content = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            fail(400, "Only UTF-8 text attachments are supported")
        return {"type": "text", "text": f"Attached file ({name}):\n{content[:8000]}"}, len(data), False
    fail(415, "Supported documents: PDF, DOCX, TXT, MD, CSV, JSON, PY and LOG")


def messages_from(body):
    incoming = body.get("messages")
    if not isinstance(incoming, list) or not 1 <= len(incoming) <= 12:
        fail(400, "Send 1–12 conversation messages")
    messages = []
    chars = 0
    images = 0
    files = 0
    file_bytes = 0
    has_pdf = False
    for msg in incoming:
        if not isinstance(msg, dict) or msg.get("role") not in ("user", "assistant"):
            fail(400, "Unsupported role")
        original = msg.get("content")
        if isinstance(original, list):
            out = []
            for part in original:
                if not isinstance(part, dict):
                    fail(400, "Unsupported media input")
                if part.get("type") == "text":
                    txt = str(part.get("text") or "")[:5000]
                    chars += len(txt)
                    out.append({"type": "text", "text": txt})
                elif part.get("type") == "file" and msg["role"] == "user":
                    files += 1
                    parsed, size, pdf = document_part(part)
                    file_bytes += size
                    has_pdf = has_pdf or pdf
                    if parsed["type"] == "text":
                        chars += len(parsed["text"])
                    out.append(parsed)
                elif part.get("type") == "image_url":
                    images += 1
                    image_url = part.get("image_url")
                    if not isinstance(image_url, dict):
                        fail(400, "Unsupported media input")
                    inline = parse_attachment(image_url.get("url"), ["image/jpeg", "image/png", "image/webp"])
                    out.append({"type": "image_url", "image_url": {"url": inline["value"]}})
                else:
                    fail(400, "Unsupported media input")
        else:
            out = str(original or "")[:5000]
            chars += len(out)
        messages.append({"role": msg["role"], "content": out})
    if chars > 14000 or images > 3 or files > 3 or file_bytes > MAX_ALL_FILES:
        fail(413, "Context too large (14,000 characters / 3 images / 7 MB of files)")
    return messages, images > 0, has_pdf


async def chat(request, identity, body, streaming=False):
    incoming, has_image, has_pdf = messages_from(body)
    all_models = await catalogue(request.app.state.http, "chat")
    model = choose(all_models, body.get("model"))
    if not model and body.get("model"):
        fail(400, "Selected model is unavailable; refresh the catalogue")
    if not model:
        model = (choose(all_models, "qwen/qwen3.7-flash") or
                 choose(all_models, "google/gemini-3.1-flash-lite") or
                 next(iter(sorted((m for m in all_models
                                   if "text" in modalities(m, "input")
                                   and "text" in modalities(m, "output")), key=cost)), None))
    if (not model or "text" not in modalities(model, "output") or
            "text" not in modalities(model, "input") or
            (has_image and "image" not in modalities(model, "input"))):
        fail(400, "Choose a compatible text/vision model")
    pricing = model.get("pricing") or {}
    try:
        input_price, output_price = float(pricing["prompt"]), float(pricing["completion"])
    except (TypeError, ValueError, KeyError):
        fail(403, "That model exceeds the AI Mesh low-cost testing policy")
    if not (0 <= input_price <= 0.0000015 and 0 <= output_price <= 0.000004):
        fail(403, "That model exceeds the AI Mesh low-cost testing policy")
    await take(identity, "chat")
    payload = {"model": model["id"],
               "messages": [{"role": "system", "content": SYSTEM}] + incoming,
               "max_tokens": 700, "temperature": 0.5, "stream": streaming}
    if has_pdf:
        payload["plugins"] = [{"id": "file-parser", "pdf": {"engine": "cloudflare-ai"}}]
    client = request.app.state.http
    if not streaming:
        r = await upstream(client, "/chat/completions", "POST", payload, timeout=90)
        data = r.json()
        answer = ((data.get("choices") or [{}])[0].get("message") or {}).get("content")
        text = answer if isinstance(answer, str) else "\n".join(
            p.get("text", "") for p in answer if isinstance(p, dict) and p.get("type") == "text"
        ) if isinstance(answer, list) else ""
        return {"model": model["id"], "text": text or "No text was returned.",
                "usage": data.get("usage"), "generation_id": data.get("id")}

    call = client.build_request("POST", BASE + "/chat/completions",
                                headers=provider_headers(), json=payload, timeout=90)
    try:
        upstream_stream = await client.send(call, stream=True)
    except httpx.HTTPError:
        fail(502, "Streaming provider unavailable")
    if not upstream_stream.is_success:
        status = upstream_stream.status_code
        await upstream_stream.aclose()
        fail(502 if status >= 500 else status, "Streaming provider request failed")

    async def events():
        def event(data):
            return "data: " + json.dumps(data) + "\n\n"
        yielded = 0
        done = False
        try:
            yield event({"type": "start", "model": model["id"]})
            async for line in upstream_stream.aiter_lines():
                if not line.startswith("data:"):
                    continue
                value = line[5:].strip()
                if value == "[DONE]":
                    done = True
                    break
                try:
                    data = json.loads(value)
                except ValueError:
                    continue
                if data.get("error"):
                    yield event({"type": "error", "message": "Provider stream error"})
                    done = True
                    break
                part = ((data.get("choices") or [{}])[0].get("delta") or {}).get("content")
                if isinstance(part, str) and part:
                    yielded += len(part)
                    if yielded > 12500:
                        raise ValueError("output too long")
                    yield event({"type": "delta", "text": part})
                if data.get("usage"):
                    yield event({"type": "usage", "usage": data["usage"]})
            if not done:
                yield event({"type": "notice", "message": "Provider stream closed"})
            yield event({"type": "done"})
        except (httpx.HTTPError, ValueError):
            yield event({"type": "error", "message": "Streaming reply interrupted"})
        finally:
            await upstream_stream.aclose()
    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"cache-control": "no-store, no-transform",
                                      "x-accel-buffering": "no"})


async def generate_image(request, identity, body):
    if os.getenv("MESH_ENABLE_IMAGE") != "true":
        fail(403, "Image generation is disabled until a provider key-level spending cap is configured")
    model = choose(await catalogue(request.app.state.http, "image"), body.get("model"))
    if not model:
        fail(400, "Choose a currently available image model")
    if body.get("confirmed") is not True:
        fail(400, "Confirm the image generation charge")
    prompt = str(body.get("prompt") or "").strip()
    if not 1 <= len(prompt) <= 1600:
        fail(400, "Image prompt must be 1–1,600 characters")
    await take(identity, "image")
    result = (await upstream(request.app.state.http, "/images", "POST",
                             {"model": model["id"], "prompt": prompt, "n": 1}, timeout=120)).json()
    try:
        data = result["data"][0]["b64_json"]
        if not isinstance(data, str) or len(data) > 7 * 1024 * 1024:
            raise ValueError()
        header = base64.b64decode(data[:48])
    except (KeyError, IndexError, ValueError):
        fail(502, "Provider returned no supported inline image")
    mime = "image/jpeg" if header[:2] == b"\xff\xd8" else "image/webp" if header[:4] == b"RIFF" else "image/png"
    return {"model": model["id"], "image": "data:" + mime + ";base64," + data, "usage": result.get("usage")}


async def transcribe(request, identity, body):
    model = choose(await catalogue(request.app.state.http, "chat"), body.get("model"))
    if not model or "transcription" not in modalities(model, "output"):
        fail(400, "Choose a transcription model")
    audio = parse_attachment(body.get("audio"), list(FORMATS))
    await take(identity, "transcribe")
    result = (await upstream(request.app.state.http, "/audio/transcriptions", "POST",
                             {"model": model["id"], "input_audio": {
                                 "data": audio["data"], "format": FORMATS[audio["mime"]]}},
                             timeout=90)).json()
    return {"text": str(result.get("text") or ""), "model": model["id"], "usage": result.get("usage")}


async def speak(request, identity, body):
    model = choose(await catalogue(request.app.state.http, "chat"), body.get("model"))
    if not model or "speech" not in modalities(model, "output"):
        fail(400, "Choose a speech model")
    text = str(body.get("text") or "").strip()
    if not 1 <= len(text) <= 1200:
        fail(400, "Speech text must be 1–1,200 characters")
    await take(identity, "speech")
    payload = {"model": model["id"], "input": text, "response_format": "mp3"}
    if model["id"].startswith("openai/"):
        payload["voice"] = "alloy"
    r = await upstream(request.app.state.http, "/audio/speech", "POST", payload, timeout=90)
    if len(r.content) > 4 * 1024 * 1024:
        fail(502, "Audio result exceeded safe output limit")
    return {"model": model["id"], "audio": "data:audio/mpeg;base64," +
            base64.b64encode(r.content).decode("ascii")}


def video_signature(job, session, until):
    secret = os.environ.get("DRAGONZPYDER_MESH_RECEIPT_SECRET", "")
    return hmac.new(secret.encode(), (session + "|" + job + "|" + str(until)).encode(),
                    hashlib.sha256).hexdigest()


async def generate_video(request, identity, body):
    if os.getenv("MESH_ENABLE_VIDEO") != "true":
        fail(403, "Video generation is disabled until a strict provider spending limit is configured")
    if body.get("confirmed") is not True:
        fail(400, "Confirm video generation cost first")
    model = choose(await catalogue(request.app.state.http, "video"), body.get("model"))
    if not model:
        fail(400, "Choose a video model")
    prompt = str(body.get("prompt") or "").strip()
    if not 1 <= len(prompt) <= 900:
        fail(400, "Video prompt must be 1–900 characters")
    durations = [n for n in model.get("supported_durations", []) if type(n) is int and 0 < n <= 5]
    if not durations:
        fail(400, "This model does not offer a short, low-cost test duration")
    resolutions = model.get("supported_resolutions") or []
    resolution = "480p" if "480p" in resolutions else "720p" if "720p" in resolutions else None
    if not resolution:
        fail(400, "This model does not offer a low-resolution test")
    await take(identity, "video")
    payload = {"model": model["id"], "prompt": prompt, "duration": durations[0],
               "resolution": resolution, "generate_audio": False}
    if "16:9" in (model.get("supported_aspect_ratios") or []):
        payload["aspect_ratio"] = "16:9"
    result = (await upstream(request.app.state.http, "/videos", "POST", payload, timeout=30)).json()
    job = result.get("id", "")
    if not isinstance(job, str) or not VIDEO_ID.fullmatch(job):
        fail(502, "Invalid provider video job identifier")
    until = int(time.time() * 1000) + 24 * 3600 * 1000
    return JSONResponse({"id": job, "status": result.get("status"),
                         "model": model["id"], "until": until,
                         "proof": video_signature(job, identity, until)}, status_code=202)


async def fetch_video(request, identity, parts):
    job = parts[2]
    if not VIDEO_ID.fullmatch(job):
        fail(400, "Invalid video job")
    try:
        until = int(request.query_params.get("until", "0"))
        proof = request.query_params.get("proof", "")
        now = int(time.time() * 1000)
        if not now <= until <= now + 26 * 3600 * 1000 or not hmac.compare_digest(proof, video_signature(job, identity, until)):
            raise ValueError()
    except ValueError:
        fail(403, "Video job does not belong to this session or has expired")
    if len(parts) == 4 and parts[3] == "content":
        try:
            r = await request.app.state.http.get(
                BASE + "/videos/" + quote(job, safe="") + "/content?index=0",
                headers={"authorization": provider_headers()["authorization"]}, timeout=120)
        except httpx.HTTPError:
            fail(502, "Video content unavailable")
        if not r.is_success or not r.headers.get("content-type", "video/mp4").startswith("video/"):
            fail(502, "Video content unavailable")
        return Response(r.content, media_type=r.headers.get("content-type", "video/mp4"),
                        headers={"cache-control": "private,no-store", "content-disposition": "inline"})
    result = (await upstream(request.app.state.http,
                             "/videos/" + quote(job, safe=""), timeout=20)).json()
    return {"id": result.get("id"), "status": result.get("status"),
            "error": result.get("error"), "usage": result.get("usage")}


async def mesh(request: Request):
    identity = await personal_session(request, request.app.state.http, request.method == "POST")
    path = request.url.path
    if request.method == "GET":
        if path == "/mesh/models":
            return await model_list(request.app.state.http)
        parts = [p for p in path.split("/") if p]
        if len(parts) in (3, 4) and parts[0:2] == ["mesh", "video"] and (
                len(parts) == 3 or parts[3] == "content"):
            return await fetch_video(request, identity, parts)
        fail(405, "Unsupported method")
    if request.method != "POST":
        fail(405, "Unsupported method")
    if path not in ("/mesh/chat", "/mesh/chat-stream", "/mesh/image",
                    "/mesh/transcribe", "/mesh/speech", "/mesh/video"):
        fail(404, "Unknown Mesh endpoint")
    if not os.getenv("DRAGONZPYDER_MESH_GATEWAY_TOKEN"):
        fail(503, "DragonZpyder inference gateway is not configured")
    if int(request.headers.get("content-length", "0") or "0") > MAX_BODY:
        fail(413, "Attachment is too large")
    raw = await request.body()
    if len(raw) > MAX_BODY:
        fail(413, "Request size limit reached")
    try:
        body = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        fail(400, "Invalid JSON request")
    if not isinstance(body, dict):
        fail(400, "Invalid request")
    if path == "/mesh/chat":
        return await chat(request, identity, body)
    if path == "/mesh/chat-stream":
        return await chat(request, identity, body, streaming=True)
    if path == "/mesh/image":
        return await generate_image(request, identity, body)
    if path == "/mesh/transcribe":
        return await transcribe(request, identity, body)
    if path == "/mesh/speech":
        return await speak(request, identity, body)
    return await generate_video(request, identity, body)
