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
