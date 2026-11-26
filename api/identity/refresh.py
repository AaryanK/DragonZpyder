"""Single-use refresh tokens, atomic rotation and family replay revocation.

Operates only with a dedicated identity PostgreSQL connection. The caller must
authenticate the authorized OAuth client. Tokens are opaque HMAC-hashed in DB.
No public endpoint is mounted by this module.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .grants import _secret_digest, OAuthGrantDenied, _registered_client, _transaction


@dataclass(frozen=True)
class IssuedRefresh:
    value: str
    expires_at: datetime


@dataclass(frozen=True)
class RotatedRefresh:
    subject: str
    audience: str
    scope: str
    value: str
    expires_at: datetime


def _now():
    return datetime.now(timezone.utc)


async def issue_refresh(conn, *, subject: str, client_id: str, redirect_uri: str,
                        scope: str, duration_days: int = 30,
                        in_transaction: bool = False) -> IssuedRefresh:
    if not 1 <= duration_days <= 30:
        raise OAuthGrantDenied("Invalid refresh lifetime")
    token = secrets.token_urlsafe(48)
    expiry = _now() + timedelta(days=duration_days)
    family = secrets.token_urlsafe(24)
    async with _transaction(conn, inside=in_transaction):
        client = await _registered_client(
            conn, client_id=client_id, redirect_uri=redirect_uri, scope=scope,
        )
        active = await conn.fetchval(
            "SELECT 1 FROM identity_accounts WHERE subject=$1 AND status='active' AND source_active=TRUE FOR UPDATE",
            subject,
        )
        if active != 1:
            raise OAuthGrantDenied("Account unavailable")
        await conn.execute(
            """INSERT INTO identity_refresh_grants
               (refresh_hash, subject, client_id, family_id, scope, audience, expires_at)
               VALUES ($1,$2,$3,$4,$5,$6,$7)""",
            _secret_digest("refresh:" + token), subject, client_id, family,
            scope, client["audience"], expiry,
        )
    return IssuedRefresh(token, expiry)


async def rotate_refresh(conn, *, token: str, client_id: str, redirect_uri: str) -> RotatedRefresh:
    if not isinstance(token, str) or not 32 <= len(token) <= 128:
        raise OAuthGrantDenied("Invalid refresh token")
    digest = _secret_digest("refresh:" + token)
    replay = False
    new_token = secrets.token_urlsafe(48)
    async with conn.transaction():
        # Serialize every refresh within the family (including simultaneous
        # reuse) by acquiring a transaction-level row lock on the family key.
        row = await conn.fetchrow(
            """SELECT subject,client_id,family_id,scope,audience,expires_at,consumed_at,revoked_at
               FROM identity_refresh_grants WHERE refresh_hash=$1""", digest,
        )
        if row is None or row["client_id"] != client_id:
            raise OAuthGrantDenied("Refresh token rejected")
        if await conn.fetchval(
            "SELECT 1 FROM identity_accounts WHERE subject=$1 AND status='active' AND source_active=TRUE FOR UPDATE",
            row["subject"],
        ) != 1:
            raise OAuthGrantDenied("Account unavailable")
        await conn.execute(
            "SELECT pg_advisory_xact_lock(hashtext($1))",
            row["family_id"],
        )
        # Re-read under the transaction lock to see any intervening rotation.
        row = await conn.fetchrow(
            """SELECT subject,client_id,family_id,scope,audience,expires_at,consumed_at,revoked_at
               FROM identity_refresh_grants WHERE refresh_hash=$1 FOR UPDATE""", digest,
        )
        if row is None:
            raise OAuthGrantDenied("Refresh token rejected")
        # Check client/redirect/audience before treating a request as replay.
        # A wrong client must not be able to revoke another client\'s family.
        if row["client_id"] != client_id:
            raise OAuthGrantDenied("Refresh token rejected")
        client = await _registered_client(
            conn, client_id=client_id, redirect_uri=redirect_uri, scope=row["scope"],
        )
        if client["audience"] != row["audience"]:
            raise OAuthGrantDenied("Client audience changed")
        # Rotation preserves the original absolute family lifetime.
        expiry = row["expires_at"]
        # A consumed token indicates theft or replay: revoke its entire family.
        if row["consumed_at"] is not None:
            await conn.execute(
                """UPDATE identity_refresh_grants SET revoked_at=now()
                   WHERE family_id=$1 AND revoked_at IS NULL""", row["family_id"],
            )
            replay = True
        else:
            if row["revoked_at"] is not None or expiry <= _now():
                raise OAuthGrantDenied("Refresh token rejected")
            active = await conn.fetchval(
                "SELECT 1 FROM identity_accounts WHERE subject=$1 AND status='active' AND source_active=TRUE",
                row["subject"],
            )
            if active != 1:
                raise OAuthGrantDenied("Account unavailable")
            updated = await conn.execute(
                """UPDATE identity_refresh_grants SET consumed_at=now()
                   WHERE refresh_hash=$1 AND consumed_at IS NULL AND revoked_at IS NULL""", digest,
            )
            if updated != "UPDATE 1":
                raise OAuthGrantDenied("Refresh token already consumed")
            await conn.execute(
                """INSERT INTO identity_refresh_grants
                   (refresh_hash,subject,client_id,family_id,scope,audience,expires_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7)""",
                _secret_digest("refresh:" + new_token), row["subject"], row["client_id"],
                row["family_id"], row["scope"], row["audience"], expiry,
            )
    # Do not raise *within* the transaction, otherwise family revocation rolls back.
    if replay:
        raise OAuthGrantDenied("Refresh token reuse detected; family revoked")
    return RotatedRefresh(
        subject=row["subject"], audience=row["audience"], scope=row["scope"],
        value=new_token, expires_at=expiry,
    )


async def revoke_refresh_family(conn, *, token: str) -> None:
    if not isinstance(token, str) or not 32 <= len(token) <= 128:
        return
    digest = _secret_digest("refresh:" + token)
    async with conn.transaction():
        family = await conn.fetchval(
            "SELECT family_id FROM identity_refresh_grants WHERE refresh_hash=$1",
            digest,
        )
        if family:
            await conn.execute("SELECT pg_advisory_xact_lock(hashtext($1))", family)
            await conn.execute(
                """UPDATE identity_refresh_grants SET revoked_at=now()
                   WHERE family_id=$1 AND revoked_at IS NULL""", family,
            )
