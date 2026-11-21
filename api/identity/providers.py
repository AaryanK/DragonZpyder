"""Verify Google and Discord provider credentials before account lookup.

This module only returns validated provider subject IDs; it never uses email
to find/create a user. OAuth state/nonce replay protection is provided by a
separate persisted, one-time login challenge. Do not expose this as an API
without the challenge store, browser binding and anti-CSRF wiring.
"""
from __future__ import annotations

import hmac
import os
import time
from dataclasses import dataclass
from typing import Any

import httpx

from .passwords import normalize_email


class ProviderProofDenied(PermissionError):
    pass


@dataclass(frozen=True)
class ProviderProof:
    provider: str
    provider_subject: str
    verified_email: str | None = None


def verify_google_identity_token(credential: str, *, expected_nonce: str) -> ProviderProof:
    """Verify Google ID token signature and claims using Google's trusted keys."""
    client_id = os.getenv("DRAGONZPYDER_IDENTITY_GOOGLE_CLIENT_ID", "").strip()
    if not client_id or not isinstance(credential, str) or not credential or len(credential) > 8192:
        raise ProviderProofDenied("Google sign-in not available")
    if not isinstance(expected_nonce, str) or len(expected_nonce) < 24:
        raise ProviderProofDenied("Google nonce is missing")
    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token
        claims: dict[str, Any] = id_token.verify_oauth2_token(
            credential, google_requests.Request(), client_id,
        )
    except Exception as exc:
        raise ProviderProofDenied("Google identity could not be verified") from exc
    if (claims.get("iss") not in ("accounts.google.com", "https://accounts.google.com")
            or claims.get("aud") != client_id
            or claims.get("email_verified") not in (True, "true")
            or not isinstance(claims.get("nonce"), str)
            or not hmac.compare_digest(claims["nonce"], expected_nonce)):
        raise ProviderProofDenied("Google identity claims rejected")
    sub = claims.get("sub")
    if not isinstance(sub, str) or not 1 <= len(sub) <= 255:
        raise ProviderProofDenied("Invalid Google subject")
    exp = claims.get("exp")
    if not isinstance(exp, int) or exp <= int(time.time()):
        raise ProviderProofDenied("Google identity expired")
    try:
        email = normalize_email(claims["email"])
    except (KeyError, ValueError, TypeError) as exc:
        raise ProviderProofDenied("Invalid verified Google email") from exc
    return ProviderProof(provider="google", provider_subject=sub, verified_email=email)


async def exchange_discord_oauth_code(
    client: httpx.AsyncClient, *, code: str, redirect_uri: str,
) -> ProviderProof:
    """Backend-only authorization-code exchange; caller must consume OAuth state.

    The Discord application secret never enters the browser, model context,
    tool registry or logs. Only a verified Discord user ID is returned.
    """
    app_id = os.getenv("DRAGONZPYDER_IDENTITY_DISCORD_CLIENT_ID", "").strip()
    app_secret = os.getenv("DRAGONZPYDER_IDENTITY_DISCORD_CLIENT_SECRET", "")
    configured_redirect = os.getenv("DRAGONZPYDER_IDENTITY_DISCORD_REDIRECT_URI", "")
    if (not app_id or len(app_secret) < 20 or not configured_redirect
            or not isinstance(code, str) or not 8 <= len(code) <= 2048
            or not isinstance(redirect_uri, str)
            or not hmac.compare_digest(redirect_uri, configured_redirect)):
        raise ProviderProofDenied("Discord login is not configured")
    try:
        response = await client.post(
            "https://discord.com/api/v10/oauth2/token",
            data={"client_id": app_id, "client_secret": app_secret, "grant_type": "authorization_code",
                  "code": code, "redirect_uri": configured_redirect},
            timeout=8.0,
            follow_redirects=False,
        )
        response.raise_for_status()
        tokens = response.json()
        if not isinstance(tokens, dict) or tokens.get("token_type", "").lower() != "bearer":
            raise ProviderProofDenied("Discord token exchange rejected")
        access_token = tokens.get("access_token")
        scope = tokens.get("scope", "")
        if (not isinstance(access_token, str) or not access_token
                or not isinstance(scope, str) or "identify" not in scope.split()):
            raise ProviderProofDenied("Discord token lacks identity scope")
        profile_response = await client.get(
            "https://discord.com/api/v10/users/@me",
            headers={"Authorization": "Bearer " + access_token},
            timeout=8.0,
            follow_redirects=False,
        )
        profile_response.raise_for_status()
        profile = profile_response.json()
    except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
        raise ProviderProofDenied("Discord identity could not be verified") from exc
    if not isinstance(profile, dict) or not isinstance(profile.get("id"), str):
        raise ProviderProofDenied("Discord returned invalid identity")
    subject = profile["id"]
    # Discord snowflakes are decimal identifiers, not emails/usernames.
    if not subject.isascii() or not subject.isdecimal() or not 10 <= len(subject) <= 25:
        raise ProviderProofDenied("Invalid Discord user ID")
    return ProviderProof(provider="discord", provider_subject=subject)


async def find_login_account(conn, proof: ProviderProof) -> str:
    """Only pre-approved login-eligible provider links can resolve accounts."""
    if proof.provider not in {"google", "discord"} or not proof.provider_subject:
        raise ProviderProofDenied("Unsupported login provider")
    row = await conn.fetchrow(
        """SELECT a.subject
           FROM identity_provider_links AS p
           JOIN identity_accounts AS a ON a.subject=p.subject
           WHERE p.provider=$1 AND p.provider_subject=$2
             AND p.source='auth' AND p.login_eligible=TRUE
             AND a.status='active' AND a.source_active=TRUE""",
        proof.provider, proof.provider_subject,
    )
    if row is None or not isinstance(row["subject"], str):
        # Never use proof.verified_email to auto-merge/create users.
        raise ProviderProofDenied("Provider is not linked to an active login")
    return row["subject"]
