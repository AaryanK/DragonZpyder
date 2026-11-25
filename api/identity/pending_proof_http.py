"""Separate, disabled-by-default proof collection for pending imports."""
from __future__ import annotations

import asyncio
import json
import os

import asyncpg
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from .http_bridge import _identity_db, _issuer
from .password_login import LoginDenied
from .pending_proofs import prove_pending_password, prove_pending_google
from .providers import ProviderProofDenied, verify_google_identity_token
from .provider_challenges import create_provider_challenge, consume_provider_challenge

router = APIRouter(prefix="/identity/v1/import-proof", tags=["identity-import-proof"])


def _proof_enabled(request):
    if os.getenv("DRAGONZPYDER_IMPORT_PROOF_ENABLED") != "1":
        raise HTTPException(404, "Not found")
    if (os.getenv("RAILWAY_ENVIRONMENT_NAME", "").lower() == "production"
            and os.getenv("DRAGONZPYDER_IMPORT_PROOF_ALLOW_PRODUCTION") != "1"):
        raise HTTPException(503, "Proof collection not approved")
    if request.headers.get("origin") != _issuer():
        raise HTTPException(403, "Origin rejected")


async def _payload(request, required):
    # Avoid model validation responses that echo submitted passwords or tokens.
    if request.headers.get("content-type", "").split(";", 1)[0].lower() != "application/json":
        raise HTTPException(415, "JSON required")
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > 12288:
            raise HTTPException(413, "Request too large")
    try:
        def unique_pairs(pairs):
            data = {}
            for key, value in pairs:
                if key in data:
                    raise ValueError("Duplicate field")
                data[key] = value
            return data
        body = json.loads(raw, object_pairs_hook=unique_pairs)
        if (not isinstance(body, dict) or set(body) != set(required)
                or any(not isinstance(body[k], str) or not 1 <= len(body[k]) <= n
                       for k,n in required.items())):
            raise ValueError("Invalid fields")
        return body
    except (ValueError, TypeError, UnicodeError):
        raise HTTPException(400, "Invalid proof request") from None


def _receipt(proof_id):
    # Not a session, grant, activation approval or bearer credential.
    return JSONResponse({"proof_reference": str(proof_id), "status": "awaiting_review"},
                        status_code=202, headers={"Cache-Control": "no-store"})


@router.post("/password", include_in_schema=False)
async def pending_password(request: Request):
    _proof_enabled(request)
    body = await _payload(request, {"email":320,"password":1024})
    try:
        async with _identity_db() as conn:
            proof_id = await prove_pending_password(conn, **body)
    except (LoginDenied, UnicodeError):
        raise HTTPException(401, "Proof rejected") from None
    except asyncpg.PostgresError:
        raise HTTPException(503, "Proof collection unavailable") from None
    return _receipt(proof_id)


@router.post("/google/start", include_in_schema=False)
async def pending_google_start(request: Request):
    _proof_enabled(request)
    client_id = os.getenv("DRAGONZPYDER_IDENTITY_GOOGLE_CLIENT_ID", "")
    if not client_id:
        raise HTTPException(503, "Google proof unavailable")
    try:
        async with _identity_db() as conn:
            challenge = await create_provider_challenge(conn, provider="google", purpose="pending_import")
    except asyncpg.PostgresError:
        raise HTTPException(503, "Proof collection unavailable") from None
    response = JSONResponse({"state":challenge.state,"nonce":challenge.nonce,"client_id":client_id},
                            headers={"Cache-Control": "no-store"})
    response.set_cookie("__Host-dz_import_proof", challenge.binding, secure=True,
                        httponly=True, samesite="lax", path="/", max_age=300)
    return response


@router.post("/google/complete", include_in_schema=False)
async def pending_google_complete(request: Request):
    _proof_enabled(request)
    body = await _payload(request, {"state":128,"credential":8192})
    try:
        async with _identity_db() as conn:
            challenge = await consume_provider_challenge(
                conn, provider="google", state=body["state"],
                binding=request.cookies.get("__Host-dz_import_proof", ""), purpose="pending_import")
        if not challenge.nonce:
            raise ProviderProofDenied("Google challenge rejected")
        proof = await asyncio.to_thread(verify_google_identity_token, body["credential"],
                                        expected_nonce=challenge.nonce)
        async with _identity_db() as conn:
            proof_id = await prove_pending_google(conn, proof)
    except ProviderProofDenied:
        raise HTTPException(401, "Proof rejected") from None
    except asyncpg.PostgresError:
        raise HTTPException(503, "Proof collection unavailable") from None
    response = _receipt(proof_id)
    response.delete_cookie("__Host-dz_import_proof", secure=True, httponly=True,
                           samesite="lax", path="/")
    return response
