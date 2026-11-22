"""Browser-facing authorization and consent for enabled identity test flows.

GET only renders UI for explicitly registered clients. No tokens are created
without an authenticated session and a separate CSRF-checked POST /authorize.
Only the existing API host serves the page; scripts stay same-origin.
"""
from __future__ import annotations

import html
import re
from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import ValidationError

from . import http_bridge as bridge
from .grants import OAuthGrantDenied, _registered_client, _validate_pkce_challenge
from .sessions import SessionDenied, resolve_browser_session
from .consent import issue_interaction

router = APIRouter(prefix="/identity/v1", tags=["identity-browser"])
_ROOT = Path(__file__).resolve().parent
_HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'self'; style-src 'self'; "
        "connect-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
    ),
}


@router.get("/authorize", include_in_schema=False)
async def interactive_authorization(request: Request):
    bridge._enabled()
    params = request.query_params
    if len(params.multi_items()) != len(set(params.keys())):
        raise HTTPException(400, "Duplicate authorization parameters")
    accepted = {
        "response_type", "client_id", "redirect_uri", "scope", "state",
        "code_challenge_method", "code_challenge", "nonce",
    }
    if set(params.keys()) - accepted:
        raise HTTPException(400, "Unknown authorization parameters")
    try:
        payload = bridge.AuthorizeInput.model_validate(dict(params))
        _validate_pkce_challenge(payload.code_challenge)
        if payload.response_type != "code" or payload.code_challenge_method != "S256":
            raise ValueError("Unsupported OAuth flow")
        if "openid" in payload.scope.split():
            if not payload.nonce or not re.fullmatch(r"[A-Za-z0-9._~-]{24,128}", payload.nonce):
                raise ValueError("OIDC nonce required")
        elif payload.nonce is not None:
            raise ValueError("Nonce without openid scope")
    except (ValidationError, ValueError, OAuthGrantDenied):
        raise HTTPException(400, "Invalid authorization request") from None

    async with bridge._identity_db() as db:
        try:
            await _registered_client(
                db, client_id=payload.client_id,
                redirect_uri=payload.redirect_uri, scope=payload.scope,
            )
        except OAuthGrantDenied:
            raise HTTPException(403, "Unregistered client or scope") from None
        try:
            authenticated_subject = await resolve_browser_session(
                db, secret=request.cookies.get("__Host-dz_identity", ""),
            )
        except SessionDenied:
            authenticated_subject = None
        ticket = (await issue_interaction(
            db, subject=authenticated_subject,
            session_secret=request.cookies.get("__Host-dz_identity", ""),
            request=payload.model_dump(exclude={"consent_ticket"}),
        )) if authenticated_subject else None

    client = html.escape(payload.client_id, quote=True)
    scope = html.escape(payload.scope, quote=True)
    authenticated = authenticated_subject is not None
    ticket_meta = ('<meta name="dz-consent-ticket" content="'
                   + html.escape(ticket, quote=True) + '">') if ticket else ""
    # Render only validated registered metadata. Never render redirect_uri,
    # state or nonce in raw HTML; the external script uses URLSearchParams.
    content = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{ticket_meta}
<title>Sign in · DragonZpyder</title>
<link rel="stylesheet" href="/identity/v1/authorize/style.css">
<script defer src="/identity/v1/authorize/interactive.js"></script>
</head>
<body>
<main>
<h1>DragonZpyder identity</h1>
<p>Continue securely to <strong>{client}</strong>.</p>
<section id="signin" {'hidden' if authenticated else ''}>
<h2>Sign in</h2>
<form id="login-form" method="post" action="/identity/v1/password/login" autocomplete="on">
<fieldset id="login-fields" disabled>
<label>Email <input name="email" type="email" autocomplete="username" required></label>
<label>Password <input name="password" type="password" autocomplete="current-password" required></label>
<button type="submit">Sign in</button>
</fieldset>
</form>
<noscript>JavaScript is required for secure sign-in. No credentials have been submitted.</noscript>
</section>
<section id="consent" {'' if authenticated else 'hidden'}>
<h2>Authorize this application</h2>
<p>Requested permissions: <strong>{scope}</strong></p>
<p>Only approve if you started this sign-in request.</p>
<button id="approve" type="button">Continue</button>
<button id="deny" type="button">Cancel</button>
</section>
<p id="status" role="status" aria-live="polite"></p>
</main>
</body>
</html>"""
    return HTMLResponse(content, headers=_HEADERS)


@router.get("/authorize/interactive.js", include_in_schema=False)
async def interactive_script():
    bridge._enabled()
    return Response(
        _ROOT.joinpath("authorize_ui.js").read_text("utf-8"),
        media_type="text/javascript", headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/authorize/style.css", include_in_schema=False)
async def interactive_styles():
    bridge._enabled()
    return Response(
        _ROOT.joinpath("authorize_ui.css").read_text("utf-8"),
        media_type="text/css", headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )
