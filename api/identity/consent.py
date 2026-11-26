"""Session-bound, single-use approval for exact registered OAuth authorization requests."""
from __future__ import annotations
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from .grants import OAuthGrantDenied, _secret_digest

_FIELDS = ("response_type", "client_id", "redirect_uri", "scope", "state",
           "code_challenge_method", "code_challenge", "nonce")

def request_hash(request: dict) -> str:
    value = {key: request.get(key) for key in _FIELDS}
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True).encode("ascii")).hexdigest()

async def issue_interaction(conn, *, subject: str, session_secret: str, request: dict) -> str:
    if not subject or not 20 <= len(session_secret) <= 128:
        raise OAuthGrantDenied("Authenticated session required")
    ticket = secrets.token_urlsafe(40)
    await conn.execute(
        """INSERT INTO identity_authorization_interactions
           (ticket_hash,subject,session_hash,request_sha256,expires_at)
           VALUES ($1,$2,$3,$4,$5)""",
        _secret_digest("consent:" + ticket), subject, _secret_digest(session_secret),
        request_hash(request), datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    return ticket

async def consume_interaction(conn, *, ticket: str | None, subject: str,
                              session_secret: str, request: dict) -> None:
    """Call inside the same transaction that inserts the authorization code."""
    if (not isinstance(ticket, str) or not 32 <= len(ticket) <= 160
            or not isinstance(session_secret, str) or not 20 <= len(session_secret) <= 128
            or not isinstance(subject, str) or not subject):
        raise OAuthGrantDenied("Consent required")
    digest = _secret_digest("consent:" + ticket)
    row = await conn.fetchrow(
        """SELECT subject,session_hash,request_sha256,expires_at,consumed_at
           FROM identity_authorization_interactions WHERE ticket_hash=$1 FOR UPDATE""",
        digest,
    )
    if (row is None or row["consumed_at"] is not None
            or row["expires_at"] <= datetime.now(timezone.utc)
            or not hmac.compare_digest(row["subject"], subject)
            or not hmac.compare_digest(row["session_hash"], _secret_digest(session_secret))
            or not hmac.compare_digest(row["request_sha256"], request_hash(request))):
        raise OAuthGrantDenied("Consent expired or mismatched")
    if await conn.execute(
        """UPDATE identity_authorization_interactions SET consumed_at=now()
           WHERE ticket_hash=$1 AND consumed_at IS NULL""", digest,
    ) != "UPDATE 1":
        raise OAuthGrantDenied("Consent already used")
