"""Password sign-in for migrated Operly identities: disabled until migration.

Never trusts a subject provided by the caller. All failures are indistinguishable
at the HTTP boundary. The credential is verified against the DB-backed hash,
including legacy PBKDF2-to-Argon2id upgrades. Rate limiting is PostgreSQL
atomic per normalized email and is shared across API replicas.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

from .grants import _secret_digest
from .passwords import normalize_email, verify_and_update_password, EmailAddressError, hash_password
from .sessions import BrowserSession, create_browser_session


class LoginDenied(PermissionError):
    pass


MAX_ATTEMPTS = 8
# Use a process-local synthetic hash to avoid a cheap missing-account path.
DUMMY_PASSWORD_HASH = hash_password('synthetic-non-account-password-proof')


async def consume_password_attempt(conn, *, normalized: str) -> None:
    digest = _secret_digest("login:" + normalized)
    # SQL upsert serializes attempts for a given account even across replicas.
    # Every attempt counts; returning success never resets the window, so
    # guessed passwords followed by a correct one do not unlock brute force.
    count = await conn.fetchval(
        """INSERT INTO identity_login_rate_limits
              (identity_digest, attempt_count, window_started_at)
           VALUES ($1, 1, now())
           ON CONFLICT (identity_digest) DO UPDATE SET
             attempt_count = CASE
               WHEN identity_login_rate_limits.window_started_at < now() - interval '15 minutes'
                 THEN 1 ELSE identity_login_rate_limits.attempt_count + 1 END,
             window_started_at = CASE
               WHEN identity_login_rate_limits.window_started_at < now() - interval '15 minutes'
                 THEN now() ELSE identity_login_rate_limits.window_started_at END
           RETURNING attempt_count""", digest,
    )
    if not isinstance(count, int) or count > MAX_ATTEMPTS:
        raise LoginDenied("Invalid credentials")


async def password_login(conn, *, email: str, password: str) -> BrowserSession:
    if not isinstance(password, str) or not password or len(password.encode("utf-8")) > 1024:
        raise LoginDenied("Invalid credentials")
    try:
        normalized = normalize_email(email)
    except EmailAddressError as error:
        raise LoginDenied("Invalid credentials") from error
    await consume_password_attempt(conn, normalized=normalized)
    row = await conn.fetchrow(
        """SELECT subject, password_hash FROM identity_accounts
           WHERE email=$1 AND source_active=TRUE AND status='active'
             AND email_verified_at IS NOT NULL""",
        normalized,
    )
    # User-controlled plaintext passwords must never enter model context,
    # logs, exception messages, tracing, or any agent tools.
    stored = row["password_hash"] if row is not None else None
    result = await asyncio.to_thread(verify_and_update_password, password, stored or DUMMY_PASSWORD_HASH)
    if not result.valid or row is None or not stored:
        raise LoginDenied("Invalid credentials")
    # Serialize credential acceptance with recovery. A hash verified before a
    # concurrent reset is not sufficient to mint a new browser session.
    async with conn.transaction():
        current = await conn.fetchrow(
            """SELECT subject,password_hash FROM identity_accounts
               WHERE email=$1 AND status='active' AND source_active
               AND email_verified_at IS NOT NULL FOR UPDATE""", normalized,
        )
        if current is None or current["subject"] != row["subject"] or current["password_hash"] != stored:
            raise LoginDenied("Invalid credentials")
        if result.upgraded_hash:
            await conn.execute(
                """UPDATE identity_accounts SET password_hash=$1
                   WHERE subject=$2 AND password_hash=$3 AND status='active' AND source_active=TRUE""",
                result.upgraded_hash, row["subject"], stored,
            )
        return await create_browser_session(conn, authenticated_subject=row["subject"])
