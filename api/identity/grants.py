"""Server-side OAuth2 Authorization Code + S256 PKCE grant machinery.

NO endpoint exposes these methods yet. The caller must already have verified
a current first-party login session. All operations require an explicit client
registration, an ACTIVE account, and scoped client permissions. Database
connection must be asyncpg and run against a dedicated identity database.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
from dataclasses import dataclass
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from .tokens import verify_pkce_s256


class OAuthGrantDenied(PermissionError):
    pass


@dataclass(frozen=True)
class AuthorizationGrant:
    code: str
    expires_at: datetime


@dataclass(frozen=True)
class RedeemedGrant:
    subject: str
    audience: str
    scope: str
    client_id: str
    nonce: str | None = None


@asynccontextmanager
async def _transaction(conn, *, inside: bool):
    if inside:
        yield
    else:
        async with conn.transaction():
            yield


def _now():
    return datetime.now(timezone.utc)


def _secret_digest(value: str) -> str:
    pepper = os.environ.get("DRAGONZPYDER_IDENTITY_GRANT_HASH_KEY", "")
    if len(pepper.encode("utf-8")) < 32:
        raise RuntimeError("Dedicated OAuth grant hash key is required")
    return hmac.new(pepper.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()


def _validate_redirect(uri: str) -> None:
    if not isinstance(uri, str) or not 12 <= len(uri) <= 2048:
        raise OAuthGrantDenied("Invalid redirect URI")
    try:
        value = urlsplit(uri)
        valid_port = value.port in (None, 443)
    except ValueError as exc:
        raise OAuthGrantDenied("Invalid redirect URI") from exc
    if (value.scheme != "https" or not value.hostname or value.username or
            value.password or value.fragment or value.hostname in ("localhost", "127.0.0.1")
            or not valid_port):
        raise OAuthGrantDenied("Only registered HTTPS redirect URIs are supported")


def _validate_pkce_challenge(challenge: str) -> None:
    if not isinstance(challenge, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", challenge):
        raise OAuthGrantDenied("S256 PKCE challenge is required")


def _validate_client_id(value: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{3,100}", value):
        raise OAuthGrantDenied("Invalid client ID")


def _scopes_allowed(asked: str, allowed: str) -> bool:
    if not isinstance(asked, str) or not asked or len(asked) > 500:
        return False
    requested = asked.split(" ")
    permitted = allowed.split(" ")
    return all(bool(x) and x in permitted for x in requested) and len(requested) == len(set(requested))


async def _registered_client(conn, *, client_id: str, redirect_uri: str, scope: str):
    _validate_client_id(client_id)
    _validate_redirect(redirect_uri)
    row = await conn.fetchrow(
        """SELECT client_id, redirect_uri, audience, allowed_scope
           FROM identity_oauth_clients WHERE client_id=$1 AND enabled=TRUE""",
        client_id,
    )
    if (row is None or not hmac.compare_digest(row["redirect_uri"], redirect_uri)
            or not _scopes_allowed(scope, row["allowed_scope"])):
        raise OAuthGrantDenied("Client, redirect or scope not authorized")
    return row


async def authorize_code(conn, *, authenticated_subject: str, client_id: str,
                         redirect_uri: str, scope: str, pkce_s256: str,
                         nonce: str | None = None) -> AuthorizationGrant:
    """A trusted interactive login handler calls this after session+CSRF checks."""
    _validate_pkce_challenge(pkce_s256)
    if "offline_access" in scope.split() and "openid" not in scope.split():
        raise OAuthGrantDenied("offline_access requires openid scope")
    if "openid" in scope.split():
        if (not isinstance(nonce, str) or not 24 <= len(nonce) <= 128
                or not re.fullmatch(r"[A-Za-z0-9._~-]+", nonce)):
            raise OAuthGrantDenied("OIDC nonce is required for openid scope")
    elif nonce is not None:
        raise OAuthGrantDenied("Nonce without openid scope")
    if not isinstance(authenticated_subject, str) or not 1 <= len(authenticated_subject) <= 160:
        raise OAuthGrantDenied("Authenticated subject required")
    async with conn.transaction():
        client = await _registered_client(conn, client_id=client_id, redirect_uri=redirect_uri, scope=scope)
        active = await conn.fetchval(
            "SELECT 1 FROM identity_accounts WHERE subject=$1 AND status='active' AND source_active=TRUE FOR UPDATE",
            authenticated_subject,
        )
        if active != 1:
            raise OAuthGrantDenied("Account is not active")
        code = secrets.token_urlsafe(48)
        deadline = _now() + timedelta(seconds=90)
        await conn.execute(
            """INSERT INTO identity_authorization_codes
               (code_hash, subject, client_id, redirect_uri, pkce_s256, scope, audience, expires_at, nonce)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)""",
            _secret_digest(code), authenticated_subject, client_id, redirect_uri,
            pkce_s256, scope, client["audience"], deadline, nonce,
        )
        return AuthorizationGrant(code=code, expires_at=deadline)


async def redeem_code(conn, *, code: str, client_id: str, redirect_uri: str,
                      pkce_verifier: str, in_transaction: bool = False) -> RedeemedGrant:
    """Atomically consume a single-use code; no token issued by this method."""
    if not isinstance(code, str) or not 20 <= len(code) <= 128:
        raise OAuthGrantDenied("Invalid authorization code")
    _validate_client_id(client_id)
    _validate_redirect(redirect_uri)
    async with _transaction(conn, inside=in_transaction):
        # Account first, then grant row: same lock order as credential reset.
        candidate = await conn.fetchrow(
            "SELECT subject FROM identity_authorization_codes WHERE code_hash=$1",
            _secret_digest(code),
        )
        if candidate is None or await conn.fetchval(
            "SELECT 1 FROM identity_accounts WHERE subject=$1 AND status='active' AND source_active=TRUE FOR UPDATE",
            candidate["subject"],
        ) != 1:
            raise OAuthGrantDenied("Authorization code rejected")
        row = await conn.fetchrow(
            """SELECT subject, client_id, redirect_uri, pkce_s256, scope, audience, nonce,
                      expires_at, consumed_at FROM identity_authorization_codes
               WHERE code_hash=$1 FOR UPDATE""",
            _secret_digest(code),
        )
        if (row is None or row["consumed_at"] is not None or row["expires_at"] <= _now()
                or not hmac.compare_digest(row["client_id"], client_id)
                or not hmac.compare_digest(row["redirect_uri"], redirect_uri)
                or not verify_pkce_s256(pkce_verifier, row["pkce_s256"])):
            raise OAuthGrantDenied("Authorization code rejected")
        client = await _registered_client(conn, client_id=client_id,
                                          redirect_uri=redirect_uri, scope=row["scope"])
        if client["audience"] != row["audience"]:
            raise OAuthGrantDenied("Client audience changed")
        active = await conn.fetchval(
            "SELECT 1 FROM identity_accounts WHERE subject=$1 AND status='active' AND source_active=TRUE",
            row["subject"],
        )
        if active != 1:
            raise OAuthGrantDenied("Account unavailable")
        updated = await conn.execute(
            """UPDATE identity_authorization_codes SET consumed_at=now()
               WHERE code_hash=$1 AND consumed_at IS NULL""", _secret_digest(code),
        )
        if updated != "UPDATE 1":
            raise OAuthGrantDenied("Authorization code already redeemed")
        return RedeemedGrant(subject=row["subject"], audience=row["audience"],
                             scope=row["scope"], client_id=row["client_id"], nonce=row["nonce"])
