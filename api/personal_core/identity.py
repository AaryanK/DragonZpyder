"""OIDC access-token verification for the future DragonZpyder personal API."""
import os
from dataclasses import dataclass
from urllib.parse import urlsplit

import jwt
from jwt import PyJWKClient


class IdentityUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class Principal:
    issuer: str
    subject: str


_jwks = None
_jwks_uri = None


def verify(token: str) -> Principal:
    issuer = os.getenv("DRAGONZPYDER_PERSONAL_OIDC_ISSUER", "").rstrip("/")
    jwks_uri = os.getenv("DRAGONZPYDER_PERSONAL_OIDC_JWKS", "")
    audience = os.getenv("DRAGONZPYDER_PERSONAL_OIDC_AUDIENCE", "")
    if not issuer or not jwks_uri or not audience:
        raise IdentityUnavailable("Central identity not configured")
    origin, key_origin = urlsplit(issuer), urlsplit(jwks_uri)
    if (origin.scheme != "https" or key_origin.scheme != "https" or
            origin.hostname != key_origin.hostname or not origin.hostname or
            origin.username or origin.password or origin.query or origin.fragment or
            key_origin.username or key_origin.password or key_origin.query or
            key_origin.fragment):
        raise IdentityUnavailable("Invalid OIDC trust configuration")
    if not isinstance(token, str) or not 1 <= len(token) <= 8192:
        raise ValueError("Invalid bearer token")
    global _jwks, _jwks_uri
    if _jwks is None or _jwks_uri != jwks_uri:
        _jwks = PyJWKClient(jwks_uri, cache_jwk_set=True, lifespan=300, timeout=5)
        _jwks_uri = jwks_uri
    try:
        key = _jwks.get_signing_key_from_jwt(token)
        claims = jwt.decode(token, key.key, algorithms=["RS256"], issuer=issuer,
                            audience=audience, leeway=30,
                            options={"require": ["sub", "exp", "iat", "iss", "aud"]})
    except (jwt.PyJWTError, ValueError) as exc:
        raise ValueError("Access token rejected") from exc
    # Scope alone cannot distinguish OAuth access tokens from OIDC ID tokens.
    # Require a positive access-token discriminator in the signed payload or
    # JWT header; an issuer without one must be adapted before onboarding.
    header = jwt.get_unverified_header(token)
    is_access = (claims.get("token_use") == "access" or
                 claims.get("typ") in ("access", "at+jwt") or
                 str(header.get("typ", "")).lower() == "at+jwt")
    if not is_access or claims.get("token_use") == "id" or claims.get("typ") in ("id", "id_token"):
        raise ValueError("A scoped OAuth access token is required")
    scope = claims.get("scope", "")
    if not isinstance(scope, str) or "dragonzpyder:personal" not in scope.split():
        raise ValueError("Missing personal API scope")
    sub = claims.get("sub")
    if not isinstance(sub, str) or not 1 <= len(sub) <= 160:
        raise ValueError("Invalid identity subject")
    return Principal(issuer=issuer, subject=sub)
