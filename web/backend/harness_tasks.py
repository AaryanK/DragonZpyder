"""Authenticated browser-to-DragonZpyder harness task bridge.

The browser only sends a Personal session cookie and anti-CSRF token to
DragonZpyder Web. Operly verifies the current identity/scope; a private
service credential is attached ONLY by the web backend. No browser-supplied
owner, API base URL, workspace or internal bearer token is forwarded.
"""
from __future__ import annotations

import hmac
import os
import re

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from uuid import UUID

from .security import OPERLY

router = APIRouter(prefix="/api/harness", tags=["personal-harness"])


class BrowserTask(BaseModel):
    request_id: str
    kind: str
    goal: str = Field(min_length=1, max_length=5000)


def _private_origin() -> str:
    origin = os.getenv("DRAGONZPYDER_API_ORIGIN", "https://api.dragonzpyder.xyz").rstrip("/")
    # Do not create an open proxy from environment or user-controlled headers.
    from urllib.parse import urlsplit
    parsed = urlsplit(origin)
    if not (parsed.scheme == "https" and parsed.hostname and
            not parsed.username and not parsed.password and not parsed.path
            and not parsed.query and not parsed.fragment):
        raise HTTPException(503, "Private harness endpoint unavailable")
    return origin


def _csrf(request: Request) -> None:
    cookie = (request.cookies.get("__Host-operly_csrf") or
              request.cookies.get("operly_csrf"))
    provided = request.headers.get("x-csrf-token", "")
    if (not cookie or not provided or len(cookie) < 12
            or not hmac.compare_digest(cookie, provided)):
        raise HTTPException(403, "Session anti-forgery check failed")


async def verified_personal_owner(request: Request) -> str:
    if not (request.cookies.get("__Host-operly_session")
            or request.cookies.get("operly_session")):
        raise HTTPException(401, "Sign in to your Personal account")
    headers = {
        "cookie": request.headers.get("cookie", ""),
        "origin": OPERLY,
        "referer": OPERLY + "/",
        "accept": "application/json",
    }
    try:
        identity, sessions = await __import__("asyncio").gather(
            request.app.state.http.get(
                OPERLY + "/api/auth/me", headers=headers, timeout=8,
            ),
            request.app.state.http.get(
                OPERLY + "/api/auth/sessions", headers=headers, timeout=8,
            ),
        )
    except httpx.HTTPError as exc:
        raise HTTPException(503, "Identity verification unavailable") from exc
    if identity.status_code != 200 or sessions.status_code != 200:
        raise HTTPException(401, "Valid Personal session required")
    try:
        account, records = identity.json(), sessions.json()
    except (ValueError, TypeError) as exc:
        raise HTTPException(503, "Invalid identity response") from exc
    if not isinstance(account, dict) or not isinstance(records, list):
        raise HTTPException(503, "Identity response unavailable")
    if not any(isinstance(s, dict) and s.get("current") is True
               and s.get("scope") == "personal" for s in records):
        raise HTTPException(403, "Personal-scoped account required")
    owner = account.get("id") or account.get("user_id") or account.get("email")
    if not isinstance(owner, str) or not 3 <= len(owner) <= 250:
        raise HTTPException(503, "Account identity unavailable")
    return owner.casefold() if "@" in owner else owner


async def private_task_request(request: Request, operation: str,
                               payload: dict) -> dict:
    if operation not in {"submit", "list", "detail", "cancel",
                         "admin/list", "admin/detail"}:
        raise HTTPException(404, "Unknown harness operation")
    token = os.getenv("DRAGONZPYDER_WEB_TASK_SERVICE_TOKEN", "")
    if len(token) < 40:
        raise HTTPException(503, "Harness tasks are not configured")
    try:
        upstream = await request.app.state.http.post(
            _private_origin() + "/internal/web-tasks/" + operation,
            json=payload,
            headers={"Authorization": "Bearer " + token,
                     "Accept": "application/json"},
            timeout=20,
        )
        if len(upstream.content) > 220000:
            raise HTTPException(502, "Harness response exceeds view limit")
        data = upstream.json()
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        raise HTTPException(502, "Harness activity service unavailable") from exc
    if not isinstance(data, dict):
        raise HTTPException(502, "Invalid harness activity response")
    if upstream.status_code >= 400:
        # Browser only receives a generic error; upstream error bodies may
        # reveal internal network, connection, or provider details.
        raise HTTPException(upstream.status_code,
                            "Harness request unavailable" if upstream.status_code >= 500
                            else "Harness request rejected")
    return data


@router.get("/tasks")
async def list_tasks(request: Request):
    owner = await verified_personal_owner(request)
    return await private_task_request(request, "list", {"owner": owner})


@router.post("/tasks")
async def create_task(payload: BrowserTask, request: Request):
    _csrf(request)
    owner = await verified_personal_owner(request)
    if payload.kind not in ("probe", "agent"):
        raise HTTPException(422, "Unsupported task type")
    try:
        if str(UUID(payload.request_id)) != payload.request_id:
            raise ValueError()
    except (TypeError, ValueError, AttributeError) as exc:
        raise HTTPException(422, "Invalid task request identity") from exc
    return await private_task_request(request, "submit", {
        "owner": owner, "request_id": payload.request_id,
        "kind": payload.kind, "goal": payload.goal,
    })


@router.get("/tasks/{task_id}")
async def read_task(task_id: str, request: Request):
    owner = await verified_personal_owner(request)
    return await private_task_request(request, "detail", {
        "owner": owner, "task_id": task_id,
    })


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str, request: Request):
    _csrf(request)
    owner = await verified_personal_owner(request)
    return await private_task_request(request, "cancel", {
        "owner": owner, "task_id": task_id,
    })
