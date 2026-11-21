"""Opaque first-party identity browser sessions, never shared across domains.

Calls that create a session MUST follow a completed password/provider login.
An active account is checked again at session creation and on every lookup.
The browser cookie must be Secure, HttpOnly, SameSite=Lax/Strict and host-only;
the CSRF token is a separate, non-HttpOnly double-submit cookie paired with
this server-side session. No agent tool can invoke these methods.
"""
from __future__ import annotations

import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .grants import _secret_digest


class SessionDenied(PermissionError):
    pass


@dataclass(frozen=True)
class BrowserSession:
    secret: str
    csrf: str
    expires_at: datetime


def _now():
    return datetime.now(timezone.utc)


async def create_browser_session(conn, *, authenticated_subject: str) -> BrowserSession:
    if not isinstance(authenticated_subject, str) or not 1 <= len(authenticated_subject) <= 160:
        raise SessionDenied("Authenticated user required")
    async with conn.transaction():
        active = await conn.fetchval(
            "SELECT 1 FROM identity_accounts WHERE subject=$1 AND status='active' AND source_active=TRUE",
            authenticated_subject,
        )
        if active != 1:
            raise SessionDenied("Account unavailable")
        secret = secrets.token_urlsafe(48)
        csrf = secrets.token_urlsafe(32)
        expiry = _now() + timedelta(days=7)
        await conn.execute(
            """INSERT INTO identity_browser_sessions
               (session_hash, csrf_hash, subject, expires_at)
               VALUES ($1, $2, $3, $4)""",
            _secret_digest(secret), _secret_digest(csrf), authenticated_subject, expiry,
        )
        return BrowserSession(secret, csrf, expiry)


async def resolve_browser_session(conn, *, secret: str, csrf: str | None = None,
                                  require_csrf: bool = False) -> str:
    if not isinstance(secret, str) or not 20 <= len(secret) <= 128:
        raise SessionDenied("Invalid browser session")
    if require_csrf and (not isinstance(csrf, str) or not 20 <= len(csrf) <= 128):
        raise SessionDenied("CSRF required")
    row = await conn.fetchrow(
        """SELECT s.subject, s.csrf_hash, s.expires_at, s.revoked_at
           FROM identity_browser_sessions AS s
           JOIN identity_accounts AS a ON a.subject=s.subject
           WHERE s.session_hash=$1 AND a.status='active' AND a.source_active=TRUE""",
        _secret_digest(secret),
    )
    if row is None or row["revoked_at"] is not None or row["expires_at"] <= _now():
        raise SessionDenied("Session expired or revoked")
    if require_csrf and not hmac.compare_digest(row["csrf_hash"], _secret_digest(csrf)):
        raise SessionDenied("CSRF mismatch")
    return row["subject"]


async def revoke_browser_session(conn, *, secret: str) -> None:
    if not isinstance(secret, str) or not 20 <= len(secret) <= 128:
        raise SessionDenied("Invalid browser session")
    await conn.execute(
        """UPDATE identity_browser_sessions SET revoked_at=now()
           WHERE session_hash=$1 AND revoked_at IS NULL""",
        _secret_digest(secret),
    )
