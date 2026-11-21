"""Disabled-by-default HTTP bridge for OAuth code grant primitives.

These routes are intentionally INCOMPLETE as an identity provider: no login,
consent screen, refresh token or OpenID id_token endpoint exists. Don't enable
in production. No user ID from request parameters is ever trusted.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

import asyncpg
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from .grants import OAuthGrantDenied, authorize_code, redeem_code
from .sessions import SessionDenied, resolve_browser_session
from .tokens import SigningIdentity, IdentityIssuerUnavailable, _origin

router = APIRouter(prefix="/identity/v1", tags=["identity-bridge"])


class AuthorizeInput(BaseModel):
    response_type: str
    client_id: str = Field(min_length=3, max_length=100)
    redirect_uri: str = Field(min_length=12, max_length=2048)
    scope: str = Field(min_length=1, max_length=500)
    state: str = Field(min_length=16, max_length=256)
    code_challenge_method: str
    code_challenge: str = Field(min_length=43, max_length=43)


def _enabled():
    if os.getenv("DRAGONZPYDER_IDENTITY_HTTP_ENABLED") != "1":
        raise HTTPException(404, "Not found")
    if (os.getenv("RAILWAY_ENVIRONMENT_NAME", "").lower() == "production"
            and os.getenv("DRAGONZPYDER_IDENTITY_ALLOW_PRODUCTION") != "1"):
        raise HTTPException(503, "Identity HTTP not approved for production")


def _issuer() -> str:
    try:
        return _origin(os.getenv("DRAGONZPYDER_IDENTITY_ISSUER", ""))
    except IdentityIssuerUnavailable:
        raise HTTPException(503, "Identity issuer unavailable") from None


@asynccontextmanager
async def _identity_db():
    dsn = os.getenv("DRAGONZPYDER_IDENTITY_DATABASE_URL", "")
    if not dsn or not dsn.startswith(("postgresql://", "postgres://")):
        raise HTTPException(503, "Identity database not configured")
    # Dedicated identity DB role; never reuse the model gateway DB credentials.
    try:
        conn = await asyncpg.connect(dsn=dsn, timeout=5, command_timeout=8)
    except (OSError, asyncpg.PostgresError, TimeoutError):
        raise HTTPException(503, "Identity database unavailable") from None
    try:
        yield conn
    finally:
        await conn.close()


@router.post("/authorize", include_in_schema=False)
async def browser_authorize(payload: AuthorizeInput, request: Request):
    _enabled()
    issuer = _issuer()
    if request.headers.get("origin") != issuer:
        raise HTTPException(403, "Origin rejected")
    if payload.response_type != "code" or payload.code_challenge_method != "S256":
        raise HTTPException(400, "Only OAuth code + S256 PKCE supported")
    session = request.cookies.get("__Host-dz_identity", "")
    csrf = request.headers.get("x-dz-csrf", "")
    try:
        async with _identity_db() as db:
            subject = await resolve_browser_session(
                db, secret=session, csrf=csrf, require_csrf=True,
            )
            grant = await authorize_code(
                db, authenticated_subject=subject, client_id=payload.client_id,
                redirect_uri=payload.redirect_uri, scope=payload.scope,
                pkce_s256=payload.code_challenge,
            )
    except (SessionDenied, OAuthGrantDenied) as exc:
        raise HTTPException(403, "Authorization denied") from exc
    # Registered redirect was validated by authorize_code; preserve any
    # pre-registered query string and never accept a fragment.
    parsed = urlsplit(payload.redirect_uri)
    query = urlencode({"code": grant.code, "state": payload.state})
    location = urlunsplit((parsed.scheme, parsed.netloc, parsed.path,
                           (parsed.query + "&" if parsed.query else "") + query, ""))
    return RedirectResponse(location, status_code=303, headers={"Cache-Control": "no-store"})


@router.post("/token", include_in_schema=False)
async def authorization_code_token(request: Request):
    _enabled()
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/x-www-form-urlencoded":
        raise HTTPException(415, "OAuth token request must be form-encoded")
    raw = await request.body()
    if len(raw) > 4096:
        raise HTTPException(413, "OAuth token request too large")
    try:
        params = parse_qs(raw.decode("ascii"), keep_blank_values=True, strict_parsing=True)
    except (UnicodeDecodeError, ValueError):
        raise HTTPException(400, "Malformed token request") from None
    required = {"grant_type", "code", "client_id", "redirect_uri", "code_verifier"}
    if set(params) != required or any(len(v) != 1 for v in params.values()):
        raise HTTPException(400, "Invalid token request fields")
    values = {name: params[name][0] for name in required}
    if values["grant_type"] != "authorization_code":
        raise HTTPException(400, "Unsupported OAuth grant type")
    try:
        signer = SigningIdentity.from_environment()
        async with _identity_db() as db:
            grant = await redeem_code(
                db, code=values["code"], client_id=values["client_id"],
                redirect_uri=values["redirect_uri"], pkce_verifier=values["code_verifier"],
            )
        token = signer.issue_access_token(
            authenticated_subject=grant.subject, audience=grant.audience, scope=grant.scope,
        )
    except IdentityIssuerUnavailable:
        raise HTTPException(503, "Identity issuer unavailable") from None
    except (OAuthGrantDenied, ValueError):
        raise HTTPException(400, "Authorization code rejected") from None
    return JSONResponse(
        {"access_token": token, "token_type": "Bearer", "expires_in": 300, "scope": grant.scope},
        headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
    )
