"""Browser-only connection endpoints; never accept model-selected URLs or credentials.

Reuses DragonZpyder identity's existing Secure HttpOnly host-only session and
CSRF verifier. Operly business auth remains separate and unchanged.
"""
from __future__ import annotations

import os
import re
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict, Field

from .mcp_connections import ConnectionDenied, require_gate, reviewed_providers
from identity.http_bridge import _identity_db
from identity.sessions import SessionDenied, resolve_browser_session

router = APIRouter(prefix="/internal/mcp", include_in_schema=False)


class BeginConnection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str = Field(default="", max_length=80)


def _enabled() -> None:
    try:
        require_gate()
    except ConnectionDenied:
        raise HTTPException(404, "Not found") from None


def _manager(request: Request):
    manager = getattr(request.app.state, "mcp_connections", None)
    if manager is None:
        raise HTTPException(503, "MCP connection store unavailable")
    return manager


async def _session(request: Request, *, changing: bool) -> tuple[str, str]:
    # Enforce current live identity status instead of trusting browser claims.
    secret = request.cookies.get("__Host-dz_identity", "")
    csrf = request.headers.get("x-dz-csrf", "")
    if changing:
        issuer = os.getenv("DRAGONZPYDER_IDENTITY_ISSUER", "").rstrip("/")
        if not issuer or request.headers.get("origin") != issuer:
            raise HTTPException(403, "Origin rejected")
    try:
        async with _identity_db() as db:
            owner = await resolve_browser_session(
                db, secret=secret, csrf=csrf if changing else None,
                require_csrf=changing,
            )
        return owner, secret
    except SessionDenied:
        raise HTTPException(401, "Active first-party browser session required") from None


@router.get("/providers")
async def providers(request: Request):
    _enabled()
    await _session(request, changing=False)
    return {"providers": [
        {"provider_id": p.provider_id, "description": p.description,
         "requested_scopes": list(p.requested_scopes)}
        for p in reviewed_providers().values()
    ]}


@router.post("/connections/{provider_id}/start")
async def start(provider_id: str, payload: BeginConnection, request: Request):
    _enabled()
    owner, session = await _session(request, changing=True)
    try:
        url = await _manager(request).begin(
            owner=owner, session_secret=session, provider_id=provider_id,
            label=payload.label,
        )
        return {"authorization_url": url}
    except ConnectionDenied:
        raise HTTPException(403, "Connection request denied") from None


@router.get("/oauth/callback", response_class=HTMLResponse)
async def callback(request: Request, state: str = "", code: str = "",
                   iss: str | None = None, error: str | None = None):
    _enabled()
    if error:
        return HTMLResponse("<h1>Connection not completed</h1>", status_code=400,
                            headers={"Cache-Control": "no-store"})
    owner, session = await _session(request, changing=False)
    try:
        await _manager(request).finish(
            owner=owner, session_secret=session, state=state, code=code,
            issuer_response=iss,
        )
    except ConnectionDenied:
        raise HTTPException(403, "OAuth callback rejected") from None
    # Immediately replace the code/state-bearing URL before showing a page.
    # No access token, refresh token, authorization code or account ID is
    # returned to browser JavaScript or placed in the clean success URL.
    return RedirectResponse("/internal/mcp/connected", status_code=303,
                            headers={"Cache-Control": "no-store",
                                     "Referrer-Policy": "no-referrer"})


@router.get("/connected", response_class=HTMLResponse)
async def connected(request: Request):
    _enabled()
    await _session(request, changing=False)
    return HTMLResponse("<h1>Connection saved</h1><p>You may close this tab.</p>",
                        headers={"Cache-Control": "no-store",
                                 "Referrer-Policy": "no-referrer"})


@router.get("/connections")
async def list_connections(request: Request):
    _enabled()
    owner, _ = await _session(request, changing=False)
    return {"connections": await _manager(request).list_connections(owner)}


@router.delete("/connections/{alias}")
async def disconnect(alias: str, request: Request):
    _enabled()
    owner, _ = await _session(request, changing=True)
    if not re.fullmatch(r"c[a-f0-9]{30}", alias):
        raise HTTPException(404, "Unknown connection")
    disconnected = await _manager(request).disconnect(owner, alias)
    if not disconnected:
        raise HTTPException(404, "Unknown connection")
    return {"disconnected": True}
