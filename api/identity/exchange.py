"""Atomic authorization-code exchange with OIDC nonce and optional refresh.

Issue tokens only after the code and registered client have been verified.
All DB mutations (code consumption + refresh creation) share one transaction.
No public unauthenticated code path may supply a subject or audience.
"""
from __future__ import annotations

import time

from .grants import OAuthGrantDenied, redeem_code
from .refresh import issue_refresh, rotate_refresh
from .tokens import SigningIdentity


async def exchange_code(
    conn, signer: SigningIdentity, *, code: str, client_id: str,
    redirect_uri: str, code_verifier: str,
) -> dict[str, str | int]:
    async with conn.transaction():
        grant = await redeem_code(
            conn, code=code, client_id=client_id,
            redirect_uri=redirect_uri, pkce_verifier=code_verifier,
            in_transaction=True,
        )
        scopes = grant.scope.split()
        if "openid" in scopes and not grant.nonce:
            raise OAuthGrantDenied("OIDC authorization code has no nonce")
        if "offline_access" in scopes and "openid" not in scopes:
            raise OAuthGrantDenied("offline_access requires openid scope")
        token = signer.issue_access_token(
            authenticated_subject=grant.subject,
            audience=grant.audience, scope=grant.scope,
        )
        result: dict[str, str | int] = {
            "access_token": token, "token_type": "Bearer",
            "expires_in": 300, "scope": grant.scope,
        }
        if "openid" in scopes:
            result["id_token"] = signer.issue_id_token(
                authenticated_subject=grant.subject,
                client_id=grant.client_id, nonce=grant.nonce, access_token=token,
            )
        if "offline_access" in scopes:
            refresh = await issue_refresh(
                conn, subject=grant.subject, client_id=grant.client_id,
                redirect_uri=redirect_uri, scope=grant.scope, in_transaction=True,
            )
            result["refresh_token"] = refresh.value
        return result


async def exchange_refresh(
    conn, signer: SigningIdentity, *, refresh_token: str,
    client_id: str, redirect_uri: str,
) -> dict[str, str | int]:
    issued_before_rotation = int(time.time())
    rotated = await rotate_refresh(
        conn, token=refresh_token, client_id=client_id,
        redirect_uri=redirect_uri,
    )
    if "offline_access" not in rotated.scope.split():
        # Never mint tokens from a refresh grant without persisted permission.
        raise OAuthGrantDenied("Missing refresh permission")
    token = signer.issue_access_token(
        authenticated_subject=rotated.subject,
        audience=rotated.audience, scope=rotated.scope, now=issued_before_rotation,
    )
    # Do not issue an ID token without an explicitly remembered auth nonce.
    return {
        "access_token": token, "token_type": "Bearer",
        "expires_in": 300, "scope": rotated.scope,
        "refresh_token": rotated.value,
    }
