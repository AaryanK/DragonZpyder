"""Explicit Google-verified signup for first-party DragonZpyder identities.

Existing Operly-linked subjects are never matched, claimed or merged by email.
The separate /google/signup route expresses explicit new-account intent;
proof signatures, client audience, nonce, state and browser binding are
validated in provider_http BEFORE calling this method.
"""
from __future__ import annotations

import os
from uuid import uuid4

import asyncpg

from .providers import ProviderProof, ProviderProofDenied


async def register_native_google_account(conn, proof: ProviderProof) -> str:
    if os.getenv("DRAGONZPYDER_NATIVE_GOOGLE_SIGNUP_ENABLED") != "1":
        raise ProviderProofDenied("Native account registration disabled")
    if (proof.provider != "google" or not proof.provider_subject
            or not proof.verified_email):
        raise ProviderProofDenied("Verified Google identity required")
    new_subject = str(uuid4())
    # Serializable identity uniqueness across replicas: both provider and
    # verified-email collisions are rejected, never auto-merged or silently
    # used to impersonate an imported/disabled identity.
    try:
        async with conn.transaction():
            await conn.execute(
                "SELECT pg_advisory_xact_lock(hashtext($1))",
                "dz-native-google:" + proof.provider_subject,
            )
            linked = await conn.fetchval(
                """SELECT 1 FROM identity_provider_links
                   WHERE provider='google' AND provider_subject=$1""",
                proof.provider_subject,
            )
            if linked is not None:
                raise ProviderProofDenied("Google identity already registered")
            email_bound = await conn.fetchval(
                "SELECT 1 FROM identity_accounts WHERE email=$1",
                proof.verified_email,
            )
            if email_bound is not None:
                raise ProviderProofDenied("Verified email already registered")
            await conn.execute(
                """INSERT INTO identity_accounts
                   (subject, source_operly_user_id, identity_origin,
                    email, password_hash, display_name, email_verified_at,
                    source_active, status)
                   VALUES ($1, NULL, 'native_google', $2, NULL,
                           'DragonZpyder user', now(), TRUE, 'active')""",
                new_subject, proof.verified_email,
            )
            await conn.execute(
                """INSERT INTO identity_provider_links
                   (subject, provider, provider_subject, source, login_eligible)
                   VALUES ($1, 'google', $2, 'auth', TRUE)""",
                new_subject, proof.provider_subject,
            )
    except (asyncpg.UniqueViolationError, asyncpg.CheckViolationError) as error:
        raise ProviderProofDenied("Native registration rejected") from error
    return new_subject
