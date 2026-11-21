"""Personal-session/CSRF enforcement shared by Mesh and realtime voice."""
import hashlib
import hmac
import json
import os
from urllib.parse import unquote, urlparse

import httpx
from fastapi import HTTPException, Request

OPERLY = os.environ.get("OPERLY_ORIGIN", "https://operly.dragonzpyder.xyz").rstrip("/")


def same_origin(request: Request):
    origin = request.headers.get("origin", "")
    host = request.headers.get("host", "")
    parsed = urlparse(origin)
    if (not parsed.hostname or parsed.netloc != host or
            (parsed.scheme != "https" and
             not (parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1")))):
        raise HTTPException(status_code=403, detail={"message": "Same-origin request required"})


def verify_csrf(request: Request):
    same_origin(request)
    csrf = request.headers.get("x-csrf-token", "")
    jar = {}
    for part in request.headers.get("cookie", "").split(";"):
        name, sep, value = part.partition("=")
        if sep:
            jar[name.strip()] = unquote(value.strip())
    valid = any(csrf and hmac.compare_digest(csrf, jar[name])
                for name in ("__Host-operly_csrf", "operly_csrf") if name in jar)
    if not valid:
        raise HTTPException(status_code=403, detail={"message": "Invalid session security token"})


async def personal_session(request: Request, client: httpx.AsyncClient, mutating=False) -> str:
    if mutating:
        verify_csrf(request)
    try:
        result = await client.get(
            OPERLY + "/api/auth/sessions",
            headers={"cookie": request.headers.get("cookie", ""), "origin": OPERLY,
                     "referer": OPERLY + "/", "accept": "application/json"}, timeout=10)
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail={"message": "Unable to verify Personal session"})
    if result.status_code != 200:
        raise HTTPException(status_code=401, detail={"message": "Sign in to DragonZpyder Personal"})
    try:
        sessions = result.json()
        current = next(s for s in sessions if isinstance(s, dict) and s.get("current")
                       and s.get("scope") == "personal" and s.get("id"))
    except (ValueError, TypeError, StopIteration):
        raise HTTPException(status_code=403, detail={"message": "Personal-only session is required"})
    return hashlib.sha256(str(current["id"]).encode()).hexdigest()


def message_error(code, message):
    return {"detail": {"message": message}}
