"""Verify pending imported identities without granting sessions or activation."""
from __future__ import annotations

import asyncio
from uuid import uuid4

from .password_login import LoginDenied, consume_password_attempt
from .passwords import normalize_email, verify_and_update_password, EmailAddressError
from .providers import ProviderProof, ProviderProofDenied


async def prove_pending_password(conn, *, email: str, password: str):
    if not isinstance(password, str) or not password or len(password.encode("utf-8")) > 1024:
        raise LoginDenied("Invalid credentials")
    try:
        normalized = normalize_email(email)
    except EmailAddressError:
        raise LoginDenied("Invalid credentials") from None
    # This statement commits separately; denied proofs still count.
    await consume_password_attempt(conn, normalized=normalized)
    row = await conn.fetchrow("""
        SELECT subject,password_hash FROM public.identity_accounts
        WHERE email=$1 AND source_active AND status='pending'
          AND identity_origin='operly_import' AND source_operly_user_id=subject
    """, normalized)
    stored = row["password_hash"] if row else None
    result = await asyncio.to_thread(verify_and_update_password, password, stored)
    if not result.valid or not row:
        raise LoginDenied("Invalid credentials")
    proof_id = uuid4()
    # Recheck the exact hash and pending state at insertion, not an earlier
    # account lookup. A proof never upgrades a hash or creates a session.
    inserted = await conn.execute("""
        INSERT INTO public.identity_import_proofs(proof_id,subject,proof_method)
        SELECT $1,subject,'password' FROM public.identity_accounts
        WHERE subject=$2 AND password_hash=$3 AND status='pending' AND source_active
          AND identity_origin='operly_import' AND source_operly_user_id=subject
    """, proof_id, row["subject"], stored)
    if inserted != "INSERT 0 1":
        raise LoginDenied("Invalid credentials")
    return proof_id


async def prove_pending_google(conn, proof: ProviderProof):
    """Only call after verifying Google signature, audience, nonce and challenge."""
    if proof.provider != "google" or not proof.provider_subject:
        raise ProviderProofDenied("Provider authentication rejected")
    proof_id = uuid4()
    inserted = await conn.execute("""
        INSERT INTO public.identity_import_proofs(proof_id,subject,proof_method)
        SELECT $1,a.subject,'google'
        FROM public.identity_provider_links p JOIN public.identity_accounts a ON a.subject=p.subject
        WHERE p.provider='google' AND p.provider_subject=$2 AND p.source='auth' AND p.login_eligible
          AND a.status='pending' AND a.source_active AND a.identity_origin='operly_import'
          AND a.source_operly_user_id=a.subject
    """, proof_id, proof.provider_subject)
    if inserted != "INSERT 0 1":
        raise ProviderProofDenied("Provider authentication rejected")
    return proof_id
