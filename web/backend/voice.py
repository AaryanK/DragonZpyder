"""Secure WebRTC SDP exchange; tool execution stays subject to Operly approvals."""
import hashlib
import json
import os
import time
from collections import defaultdict

import httpx
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, Response

from .security import personal_session, verify_csrf

_counts = defaultdict(lambda: {"since": 0, "count": 0})

INSTRUCTIONS = (
    "You are DragonZpyder, a friendly and efficient realtime voice companion. "
    "Speak naturally and allow interruptions. If the user asks you to take action "
    "through connected apps, use delegate_personal_task, which goes through "
    "existing Operly permissions and approvals. Never claim a task completed "
    "without confirmation. Pending approvals require human review in the "
    "Personal workspace. Do not pretend to see the screen."
)


async def realtime(request: Request):
    if request.method != "POST":
        return JSONResponse({"detail": {"message": "POST required"}}, status_code=405)
    verify_csrf(request)
    if request.headers.get("content-type", "").split(";", 1)[0].lower() != "application/sdp":
        raise HTTPException(status_code=415, detail={"message": "Expected application/sdp"})
    if int(request.headers.get("content-length", "0") or "0") > 65536:
        raise HTTPException(status_code=413, detail={"message": "SDP offer too large"})
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise HTTPException(status_code=503, detail={"message": "Live voice is not configured"})
    client = request.app.state.http
    await personal_session(request, client)
    offer = await request.body()
    if (len(offer) > 65536 or not offer.startswith(b"v=0") or b"\nm=audio " not in offer):
        raise HTTPException(status_code=400, detail={"message": "Invalid SDP offer"})
    identity = hashlib.sha256(request.headers.get("cookie", "").encode()).hexdigest()
    now = time.monotonic()
    record = _counts[identity]
    if now - record["since"] >= 3600:
        record.update(since=now, count=0)
    allowed = max(1, min(30, int(os.environ.get("REALTIME_SESSIONS_PER_HOUR", "6"))))
    if record["count"] >= allowed:
        raise HTTPException(status_code=429, detail={"message": "Voice session limit reached"})
    record["count"] += 1
    if len(_counts) > 5000:
        for k, v in list(_counts.items()):
            if now - v["since"] >= 3600:
                del _counts[k]
    session = {
        "type": "realtime", "model": os.getenv("OPENAI_REALTIME_MODEL", "gpt-realtime-2.1"),
        "instructions": INSTRUCTIONS,
        "audio": {
            "input": {"turn_detection": {"type": "server_vad", "create_response": True, "interrupt_response": True},
                      "transcription": {"model": "gpt-4o-mini-transcribe"}},
            "output": {"voice": "marin"}
        },
        "tools": [{
            "type": "function", "name": "delegate_personal_task",
            "description": "Send an authorised personal task to the existing Operly agent. Does not approve consequential actions.",
            "parameters": {"type": "object", "properties": {"request": {"type": "string"}},
                           "required": ["request"], "additionalProperties": False}
        }]
    }
    try:
        upstream = await client.post(
            "https://api.openai.com/v1/realtime/calls",
            files={"sdp": (None, offer.decode("utf-8")), "session": (None, json.dumps(session))},
            headers={"authorization": "Bearer " + key,
                     "OpenAI-Safety-Identifier": identity[:32]}, timeout=30)
    except (httpx.HTTPError, UnicodeDecodeError):
        raise HTTPException(status_code=502, detail={"message": "Could not establish live voice"})
    if upstream.status_code != 200:
        raise HTTPException(status_code=502, detail={"message": "Voice provider refused session (" + str(upstream.status_code) + ")"})
    return Response(content=upstream.content, media_type="application/sdp",
                    headers={"cache-control": "no-store", "x-content-type-options": "nosniff"})
