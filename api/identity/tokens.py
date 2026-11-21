"""Isolated RS256 access-token issuer primitives for the future DragonZpyder IDP.

No route accepts browser credentials or issues tokens. Call issue_access_token only
after a separately audited authenticated session and active account check. The
private signing key must never enter an agent, sandbox or inference prompt.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


class IdentityIssuerUnavailable(RuntimeError):
    pass


def _origin(value: str) -> str:
    if not isinstance(value, str) or len(value) > 255:
        raise IdentityIssuerUnavailable("Invalid issuer")
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or
            parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/")):
        raise IdentityIssuerUnavailable("Identity issuer must be an HTTPS origin")
    return value.rstrip("/")


def pkce_challenge(verifier: str) -> str:
    """RFC 7636 S256 (never permit PKCE plain fallback)."""
    if (not isinstance(verifier, str) or not 43 <= len(verifier) <= 128 or
            any(ch not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~" for ch in verifier)):
        raise ValueError("Invalid PKCE verifier")
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")


def verify_pkce_s256(verifier: str, expected_challenge: str) -> bool:
    if not isinstance(expected_challenge, str) or len(expected_challenge) != 43:
        return False
    try:
        return hmac.compare_digest(pkce_challenge(verifier), expected_challenge)
    except ValueError:
        return False


def _b64(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


@dataclass(frozen=True)
class SigningIdentity:
    issuer: str
    kid: str
    private_key_pem: bytes

    @classmethod
    def from_environment(cls) -> "SigningIdentity":
        issuer = _origin(os.getenv("DRAGONZPYDER_IDENTITY_ISSUER", ""))
        kid = os.getenv("DRAGONZPYDER_IDENTITY_SIGNING_KID", "")
        key = os.getenv("DRAGONZPYDER_IDENTITY_SIGNING_KEY_PEM", "").replace("\\n", "\n").encode()
        if not kid or len(kid) > 96 or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for ch in kid):
            raise IdentityIssuerUnavailable("Signing key ID missing or invalid")
        try:
            obj = serialization.load_pem_private_key(key, password=None)
        except (ValueError, TypeError) as exc:
            raise IdentityIssuerUnavailable("Signing key unavailable") from exc
        if not isinstance(obj, rsa.RSAPrivateKey) or obj.key_size < 3072:
            raise IdentityIssuerUnavailable("3072-bit or stronger RSA signing key required")
        return cls(issuer=issuer, kid=kid, private_key_pem=key)

    def jwk(self) -> dict:
        try:
            private = serialization.load_pem_private_key(self.private_key_pem, password=None)
        except (ValueError, TypeError) as exc:
            raise IdentityIssuerUnavailable("Signing key invalid") from exc
        if not isinstance(private, rsa.RSAPrivateKey) or private.key_size < 3072:
            raise IdentityIssuerUnavailable("Signing key too weak")
        public = private.public_key().public_numbers()
        return {"kty": "RSA", "use": "sig", "kid": self.kid, "alg": "RS256",
                "n": _b64(public.n), "e": _b64(public.e)}

    def issue_access_token(self, *, authenticated_subject: str, audience: str,
                           scope: str, now: int | None = None, lifetime_seconds: int = 300) -> str:
        if not isinstance(authenticated_subject, str) or not 1 <= len(authenticated_subject) <= 160:
            raise ValueError("Invalid authenticated subject")
        if not isinstance(audience, str) or not 1 <= len(audience) <= 150:
            raise ValueError("Invalid audience")
        if not isinstance(scope, str) or not scope or len(scope) > 500:
            raise ValueError("Invalid scope")
        if not isinstance(lifetime_seconds, int) or not 1 <= lifetime_seconds <= 300:
            raise ValueError("Access tokens must expire in five minutes or less")
        issued = int(time.time()) if now is None else now
        return jwt.encode(
            {"iss": self.issuer, "sub": authenticated_subject, "aud": audience,
             "iat": issued, "nbf": issued, "exp": issued + lifetime_seconds,
             "jti": secrets.token_urlsafe(24), "token_use": "access",
             "scope": scope, "typ": "at+jwt"},
            self.private_key_pem, algorithm="RS256",
            headers={"kid": self.kid, "typ": "at+jwt"},
        )

    def issue_id_token(self, *, authenticated_subject: str, client_id: str,
                       nonce: str, access_token: str, now: int | None = None) -> str:
        """OIDC ID token, always audience-bound to the registered client.

        Nonce originates from the persisted authorization-code request, never
        from /token request parameters. at_hash binds the paired access token.
        """
        if not isinstance(authenticated_subject, str) or not 1 <= len(authenticated_subject) <= 160:
            raise ValueError("Invalid authenticated subject")
        if (not isinstance(client_id, str) or not 3 <= len(client_id) <= 100
                or any(ch not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"
                       for ch in client_id)):
            raise ValueError("Invalid OIDC client")
        if (not isinstance(nonce, str) or not 24 <= len(nonce) <= 128
                or any(ch not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
                       for ch in nonce)):
            raise ValueError("Invalid OIDC nonce")
        if not isinstance(access_token, str) or not 16 <= len(access_token) <= 8192:
            raise ValueError("Access token required for at_hash")
        now_seconds = int(time.time()) if now is None else now
        access_digest = hashlib.sha256(access_token.encode("ascii")).digest()
        at_hash = base64.urlsafe_b64encode(access_digest[:16]).rstrip(b"=").decode("ascii")
        return jwt.encode(
            {"iss": self.issuer, "sub": authenticated_subject, "aud": client_id,
             "iat": now_seconds, "exp": now_seconds + 300,
             "nonce": nonce, "at_hash": at_hash, "token_use": "id"},
            self.private_key_pem, algorithm="RS256",
            headers={"kid": self.kid, "typ": "JWT"},
        )
