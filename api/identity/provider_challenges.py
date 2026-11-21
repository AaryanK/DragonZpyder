"""One-time, browser-bound challenge storage for Google/Discord sign-in."""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .grants import _secret_digest
from .providers import ProviderProofDenied


@dataclass(frozen=True)
class ProviderChallenge:
    provider: str
    state: str
    binding: str
    nonce: str | None


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def create_provider_challenge(conn, *, provider: str) -> ProviderChallenge:
    if provider not in ("google", "discord"):
        raise ProviderProofDenied("Unsupported provider")
    state = secrets.token_urlsafe(40)
    binding = secrets.token_urlsafe(40)
    nonce = secrets.token_urlsafe(32) if provider == "google" else None
    await conn.execute(
        """INSERT INTO identity_provider_challenges
           (state_hash, binding_hash, provider, nonce, expires_at)
           VALUES ($1, $2, $3, $4, $5)""",
        _secret_digest("state:" + state), _secret_digest("binding:" + binding),
        provider, nonce, _now() + timedelta(minutes=5),
    )
    return ProviderChallenge(provider, state, binding, nonce)


async def consume_provider_challenge(conn, *, provider: str, state: str,
                                     binding: str) -> ProviderChallenge:
    if (provider not in ("google", "discord") or not isinstance(state, str)
            or not 40 <= len(state) <= 128 or not isinstance(binding, str)
            or not 40 <= len(binding) <= 128):
        raise ProviderProofDenied("Login challenge missing")
    digest = _secret_digest("state:" + state)
    bound = _secret_digest("binding:" + binding)
    # Atomic UPDATE is concurrency-safe: only one request can consume it.
    row = await conn.fetchrow(
        """UPDATE identity_provider_challenges SET consumed_at=now()
           WHERE state_hash=$1 AND binding_hash=$2 AND provider=$3
             AND consumed_at IS NULL AND expires_at>now()
           RETURNING nonce""", digest, bound, provider,
    )
    if row is None:
        raise ProviderProofDenied("Login challenge expired or used")
    return ProviderChallenge(provider=provider, state=state, binding=binding,
                             nonce=row["nonce"])
