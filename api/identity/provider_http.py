"""Feature-gated Google/Discord login, only for pre-linked ACTIVE accounts.

No signup or account merging. Login challenges are persisted, browser bound
and consumed once. Google requires signed ID token and nonce; Discord requires
server-to-server OAuth code exchange and state-bound browser callback.
"""
from __future__ import annotations

import os
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from .http_bridge import _enabled, _identity_db, _issuer
from .provider_challenges import create_provider_challenge, consume_provider_challenge
from .providers import (ProviderProofDenied, verify_google_identity_token,
                        exchange_discord_oauth_code, find_login_account)
from .sessions import create_browser_session
from .native_signup import register_native_google_account
from .profile_avatar import save_google_avatar

router = APIRouter(prefix="/identity/v1/provider", tags=["identity-provider"])


def _origin_check(request: Request) -> None:
    if request.headers.get("origin") != _issuer():
        raise HTTPException(403, "Origin rejected")


def _success(session):
    response = JSONResponse({"authenticated": True}, headers={"Cache-Control": "no-store"})
    response.set_cookie("__Host-dz_identity", session.secret, secure=True,
                        httponly=True, samesite="lax", path="/", max_age=604800)
    response.set_cookie("__Host-dz_csrf", session.csrf, secure=True,
                        httponly=False, samesite="lax", path="/", max_age=604800)
    response.delete_cookie("__Host-dz_provider", secure=True, httponly=True,
                           samesite="lax", path="/")
    return response


@router.post("/{provider}/start", include_in_schema=False)
async def start_provider(provider: str, request: Request):
    _enabled()
    _origin_check(request)
    if provider not in ("google", "discord"):
        raise HTTPException(404, "Unsupported provider")
    async with _identity_db() as conn:
        challenge = await create_provider_challenge(conn, provider=provider)
    data = {"provider": provider, "state": challenge.state}
    if provider == "google":
        if not os.getenv("DRAGONZPYDER_IDENTITY_GOOGLE_CLIENT_ID"):
            raise HTTPException(503, "Google login unavailable")
        data["nonce"] = challenge.nonce
        data["client_id"] = os.getenv("DRAGONZPYDER_IDENTITY_GOOGLE_CLIENT_ID")
    else:
        client_id = os.getenv("DRAGONZPYDER_IDENTITY_DISCORD_CLIENT_ID", "")
        redirect = _issuer() + "/identity/v1/provider/discord/callback"
        if not client_id or os.getenv("DRAGONZPYDER_IDENTITY_DISCORD_REDIRECT_URI") != redirect:
            raise HTTPException(503, "Discord login unavailable")
        data["authorization_url"] = "https://discord.com/oauth2/authorize?" + urlencode({
            "client_id": client_id, "redirect_uri": redirect, "response_type": "code",
            "scope": "identify", "state": challenge.state,
        })
    response = JSONResponse(data, headers={"Cache-Control": "no-store"})
    response.set_cookie("__Host-dz_provider", challenge.binding, secure=True,
                        httponly=True, samesite="lax", path="/", max_age=300)
    return response


class GoogleComplete(BaseModel):
    state: str = Field(min_length=40, max_length=128)
    credential: str = Field(min_length=1, max_length=8192)


async def _google_login_or_signup(payload: GoogleComplete, request: Request, *, register: bool):
    _enabled()
    _origin_check(request)
    try:
        async with _identity_db() as conn:
            challenge = await consume_provider_challenge(
                conn, provider="google", state=payload.state,
                binding=request.cookies.get("__Host-dz_provider", ""),
            )
        if challenge.nonce is None:
            raise ProviderProofDenied("Google nonce missing")
        proof = verify_google_identity_token(payload.credential, expected_nonce=challenge.nonce)
        async with _identity_db() as conn:
            subject = (await register_native_google_account(conn, proof)
                       if register else await find_login_account(conn, proof))
            await save_google_avatar(conn, subject, proof)
            session = await create_browser_session(conn, authenticated_subject=subject)
    except ProviderProofDenied:
        raise HTTPException(401, "Provider authentication rejected") from None
    return _success(session)


@router.post("/google/complete", include_in_schema=False)
async def complete_google(payload: GoogleComplete, request: Request):
    return await _google_login_or_signup(payload, request, register=False)


@router.post("/google/signup", include_in_schema=False)
async def signup_google(payload: GoogleComplete, request: Request):
    # Explicit new-account intent; an existing email/provider ID is never
    # matched to another account or silently merged by signup.
    return await _google_login_or_signup(payload, request, register=True)


@router.get("/discord/callback", include_in_schema=False)
async def complete_discord(request: Request, code: str = "", state: str = ""):
    _enabled()
    try:
        async with _identity_db() as conn:
            await consume_provider_challenge(
                conn, provider="discord", state=state,
                binding=request.cookies.get("__Host-dz_provider", ""),
            )
        async with httpx.AsyncClient() as client:
            proof = await exchange_discord_oauth_code(
                client, code=code,
                redirect_uri=_issuer() + "/identity/v1/provider/discord/callback",
            )
        async with _identity_db() as conn:
            subject = await find_login_account(conn, proof)
            session = await create_browser_session(conn, authenticated_subject=subject)
    except ProviderProofDenied:
        raise HTTPException(401, "Provider authentication rejected") from None
    return _success(session)
