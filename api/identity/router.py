"""Read-only JWKS for the future identity issuer; disabled by default.

This module never provides token issuance or authentication. Production OIDC
discovery must wait for fully implemented /authorize and /token endpoints.
"""
import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from identity.tokens import IdentityIssuerUnavailable, SigningIdentity

router = APIRouter()


@router.get("/.well-known/jwks.json", include_in_schema=False)
async def identity_jwks():
    if os.getenv("DRAGONZPYDER_IDENTITY_JWKS_ENABLED") != "1":
        raise HTTPException(404, "Not found")
    try:
        signer = SigningIdentity.from_environment()
        key = signer.jwk()
    except IdentityIssuerUnavailable:
        raise HTTPException(503, "Identity signing configuration unavailable") from None
    return JSONResponse({"keys": [key]}, headers={"Cache-Control": "public, max-age=60"})


@router.get("/.well-known/openid-configuration", include_in_schema=False)
async def oidc_discovery():
    # Publish only when both the interactive browser flow and JWKS are opted in.
    if (os.getenv("DRAGONZPYDER_IDENTITY_HTTP_ENABLED") != "1"
            or os.getenv("DRAGONZPYDER_IDENTITY_JWKS_ENABLED") != "1"):
        raise HTTPException(404, "Not found")
    from identity.http_bridge import _enabled
    _enabled()
    try:
        issuer = SigningIdentity.from_environment().issuer
    except IdentityIssuerUnavailable:
        raise HTTPException(503, "Identity signing configuration unavailable") from None
    return JSONResponse({
        "issuer": issuer,
        "authorization_endpoint": issuer + "/identity/v1/authorize",
        "token_endpoint": issuer + "/identity/v1/token",
        "jwks_uri": issuer + "/.well-known/jwks.json",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["RS256"],
        "token_endpoint_auth_methods_supported": ["none"],
        "code_challenge_methods_supported": ["S256"],
        "scopes_supported": ["openid", "offline_access", "operly:access"],
    }, headers={"Cache-Control": "public, max-age=60", "X-Content-Type-Options": "nosniff"})
