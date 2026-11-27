"""Disabled-by-default HTTP bridge for OAuth code grant primitives.

These routes are intentionally INCOMPLETE as an identity provider: no login,
consent screen, refresh token or OpenID id_token endpoint exists. Don't enable
in production. No user ID from request parameters is ever trusted.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

import asyncpg
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from .grants import OAuthGrantDenied, authorize_code
from .consent import consume_interaction
from .exchange import exchange_code, exchange_refresh
from .sessions import SessionDenied, resolve_browser_session
from .tokens import SigningIdentity, IdentityIssuerUnavailable, _origin

router = APIRouter(prefix="/identity/v1", tags=["identity-bridge"])


class AuthorizeInput(BaseModel):
    response_type: str
    client_id: str = Field(min_length=3, max_length=100)
    redirect_uri: str = Field(min_length=12, max_length=2048)
    scope: str = Field(min_length=1, max_length=500)
    state: str = Field(min_length=16, max_length=256)
    code_challenge_method: str
    code_challenge: str = Field(min_length=43, max_length=43)
    nonce: str | None = Field(default=None, min_length=24, max_length=128)
    consent_ticket: str | None = Field(default=None, min_length=32, max_length=160)


def _enabled():
    if os.getenv("DRAGONZPYDER_IDENTITY_HTTP_ENABLED") != "1":
        raise HTTPException(404, "Not found")
    if (os.getenv("RAILWAY_ENVIRONMENT_NAME", "").lower() == "production"
            and os.getenv("DRAGONZPYDER_IDENTITY_ALLOW_PRODUCTION") != "1"):
        raise HTTPException(503, "Identity HTTP not approved for production")


def _issuer() -> str:
    try:
        return _origin(os.getenv("DRAGONZPYDER_IDENTITY_ISSUER", ""))
    except IdentityIssuerUnavailable:
        raise HTTPException(503, "Identity issuer unavailable") from None


async def _restricted_identity_role(conn):
    # A username is not proof of privileges. Check effective server role,
    # memberships (including SET ROLE), ownership, and protected mutations.
    allowed = await conn.fetchval("""
        SELECT current_user = 'dz_identity_api' AND session_user = current_user
          AND NOT (r.rolsuper OR r.rolcreaterole OR r.rolcreatedb
                   OR r.rolreplication OR r.rolbypassrls OR r.rolinherit)
          AND NOT EXISTS (SELECT 1 FROM pg_auth_members m WHERE m.member=r.oid)
          AND NOT EXISTS (SELECT 1 FROM pg_database d WHERE d.datname=current_database() AND d.datdba=r.oid)
          AND NOT EXISTS (SELECT 1 FROM pg_namespace n WHERE n.nspname='public' AND n.nspowner=r.oid)
          AND NOT EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                          WHERE n.nspname='public' AND c.relowner=r.oid)
          AND NOT has_database_privilege(current_user,current_database(),'CREATE')
          AND NOT has_database_privilege(current_user,current_database(),'TEMPORARY')
          AND NOT has_schema_privilege(current_user,'public','CREATE')
          AND NOT has_column_privilege(current_user,'public.identity_accounts','status','UPDATE')
          AND NOT has_column_privilege(current_user,'public.identity_accounts','source_active','UPDATE')
          AND NOT has_column_privilege(current_user,'public.identity_accounts','identity_origin','UPDATE')
          AND NOT has_column_privilege(current_user,'public.identity_accounts','source_operly_user_id','UPDATE')
          AND NOT has_column_privilege(current_user,'public.identity_accounts','email','UPDATE')
          AND NOT EXISTS (
              SELECT 1 FROM pg_attribute a
              WHERE a.attrelid=to_regclass('public.identity_accounts')
                AND a.attname IN ('operator_test_expires_at','operator_test_provisioned_by')
                AND NOT a.attisdropped
                AND (has_column_privilege(current_user,a.attrelid,a.attnum,'UPDATE')
                     OR has_column_privilege(current_user,a.attrelid,a.attnum,'INSERT')))
          AND NOT EXISTS (
              SELECT 1 FROM pg_proc p
              WHERE p.oid=to_regprocedure('public.provision_operator_test_identity(uuid,text,integer)')
                AND has_function_privilege(current_user,p.oid,'EXECUTE'))
          AND NOT has_any_column_privilege(current_user,'public.identity_oauth_clients','UPDATE')
          AND NOT has_any_column_privilege(current_user,'public.identity_oauth_clients','INSERT')
          AND NOT has_table_privilege(current_user,'public.identity_accounts','DELETE,TRUNCATE')
          AND NOT has_table_privilege(current_user,'public.identity_provider_links','DELETE,TRUNCATE')
          AND NOT has_any_column_privilege(current_user,'public.identity_provider_links','UPDATE')
          AND NOT EXISTS (
              SELECT 1 FROM pg_attribute a
              WHERE a.attrelid=to_regclass('public.identity_accounts')
                AND a.attname='import_activation_receipt_id' AND NOT a.attisdropped
                AND (has_column_privilege(current_user,a.attrelid,a.attnum,'UPDATE')
                     OR has_column_privilege(current_user,a.attrelid,a.attnum,'INSERT')))
          AND NOT EXISTS (
              SELECT 1 FROM pg_class c
              WHERE c.oid=to_regclass('public.identity_import_activation_receipts')
                AND (has_any_column_privilege(current_user,c.oid,'INSERT,UPDATE')
                     OR has_table_privilege(current_user,c.oid,'DELETE,TRUNCATE')))
          AND NOT EXISTS (
              SELECT 1 FROM pg_proc p
              WHERE p.oid=to_regprocedure('public.approve_imported_identity(text,uuid)')
                AND has_function_privilege(current_user,p.oid,'EXECUTE'))
          AND NOT EXISTS (
              SELECT 1 FROM pg_class c
              WHERE c.oid=to_regclass('public.identity_import_proofs')
                AND (has_any_column_privilege(current_user,c.oid,'UPDATE')
                     OR has_table_privilege(current_user,c.oid,'DELETE,TRUNCATE')
                     OR has_column_privilege(current_user,c.oid,'proved_at','INSERT')
                     OR NOT c.relrowsecurity))
          AND (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
               WHERE n.nspname='public' AND c.relname IN ('identity_accounts','identity_provider_links')
                 AND c.relrowsecurity)=2
        FROM pg_roles r WHERE r.rolname=current_user
    """)
    if allowed is not True:
        raise HTTPException(503, "Restricted identity database role required")


@asynccontextmanager
async def _identity_db():
    dsn = os.getenv("DRAGONZPYDER_IDENTITY_DATABASE_URL", "")
    if not dsn or not dsn.startswith(("postgresql://", "postgres://")):
        raise HTTPException(503, "Identity database not configured")
    # A Railway Postgres template initially exposes a superuser DATABASE_URL.
    # It may install the schema, but it must NEVER become the live identity
    # application's production credential. Separate roles and GRANTs are needed.
    if os.getenv("RAILWAY_ENVIRONMENT_NAME", "").lower() == "production":
        try:
            user = urlsplit(dsn).username
        except ValueError:
            raise HTTPException(503, "Invalid identity database URL") from None
        if user != "dz_identity_api":
            raise HTTPException(503, "Restricted identity database role required")
    # Dedicated identity DB role; never reuse the model gateway DB credentials.
    try:
        conn = await asyncpg.connect(dsn=dsn, timeout=5, command_timeout=8)
    except (OSError, asyncpg.PostgresError, TimeoutError):
        raise HTTPException(503, "Identity database unavailable") from None
    try:
        if os.getenv("RAILWAY_ENVIRONMENT_NAME", "").lower() == "production":
            try:
                await _restricted_identity_role(conn)
            except (OSError, asyncpg.PostgresError, TimeoutError):
                raise HTTPException(503, "Restricted identity database role required") from None
        yield conn
    finally:
        await conn.close()


@router.post("/authorize", include_in_schema=False)
async def browser_authorize(payload: AuthorizeInput, request: Request):
    _enabled()
    issuer = _issuer()
    if request.headers.get("origin") != issuer:
        raise HTTPException(403, "Origin rejected")
    if payload.response_type != "code" or payload.code_challenge_method != "S256":
        raise HTTPException(400, "Only OAuth code + S256 PKCE supported")
    session = request.cookies.get("__Host-dz_identity", "")
    csrf = request.headers.get("x-dz-csrf", "")
    try:
        async with _identity_db() as db:
            subject = await resolve_browser_session(
                db, secret=session, csrf=csrf, require_csrf=True,
            )
            async with db.transaction():
                if await db.fetchval(
                    "SELECT 1 FROM identity_accounts WHERE subject=$1 AND status='active' AND source_active=TRUE FOR UPDATE",
                    subject,
                ) != 1:
                    raise SessionDenied("Account unavailable")
                # Recheck after acquiring the same account lock as reset.
                if await resolve_browser_session(db,secret=session,csrf=csrf,require_csrf=True)!=subject:
                    raise SessionDenied("Session changed")
                await consume_interaction(
                    db, ticket=payload.consent_ticket, subject=subject,
                    session_secret=session,
                    request=payload.model_dump(exclude={"consent_ticket"}),
                )
                grant = await authorize_code(
                    db, authenticated_subject=subject, client_id=payload.client_id,
                    redirect_uri=payload.redirect_uri, scope=payload.scope,
                    pkce_s256=payload.code_challenge, nonce=payload.nonce,
                )
    except (SessionDenied, OAuthGrantDenied) as exc:
        raise HTTPException(403, "Authorization denied") from exc
    # Registered redirect was validated by authorize_code; preserve any
    # pre-registered query string and never accept a fragment.
    parsed = urlsplit(payload.redirect_uri)
    query = urlencode({"code": grant.code, "state": payload.state})
    location = urlunsplit((parsed.scheme, parsed.netloc, parsed.path,
                           (parsed.query + "&" if parsed.query else "") + query, ""))
    if "application/json" in request.headers.get("accept", ""):
        # Same-origin consent UI needs an explicit redirect URL because fetch()
        # cannot expose a cross-origin 303 Location to JavaScript.
        return JSONResponse(
            {"redirect_url": location},
            headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
        )
    return RedirectResponse(location, status_code=303, headers={
        "Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
    })


@router.post("/token", include_in_schema=False)
async def authorization_code_token(request: Request):
    _enabled()
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/x-www-form-urlencoded":
        raise HTTPException(415, "OAuth token request must be form-encoded")
    raw = await request.body()
    if len(raw) > 4096:
        raise HTTPException(413, "OAuth token request too large")
    try:
        params = parse_qs(raw.decode("ascii"), keep_blank_values=True, strict_parsing=True)
    except (UnicodeDecodeError, ValueError):
        raise HTTPException(400, "Malformed token request") from None
    values = {key: items[0] for key, items in params.items() if len(items) == 1}
    if len(values) != len(params) or "grant_type" not in values:
        raise HTTPException(400, "Invalid token request fields")
    code_fields = {"grant_type", "code", "client_id", "redirect_uri", "code_verifier"}
    refresh_fields = {"grant_type", "refresh_token", "client_id", "redirect_uri"}
    kind = values["grant_type"]
    if (kind == "authorization_code" and set(values) != code_fields
            or kind == "refresh_token" and set(values) != refresh_fields
            or kind not in ("authorization_code", "refresh_token")):
        raise HTTPException(400, "Unsupported or invalid OAuth grant")
    try:
        signer = SigningIdentity.from_environment()
        async with _identity_db() as db:
            if kind == "authorization_code":
                result = await exchange_code(
                    db, signer, code=values["code"], client_id=values["client_id"],
                    redirect_uri=values["redirect_uri"], code_verifier=values["code_verifier"],
                )
            else:
                result = await exchange_refresh(
                    db, signer, refresh_token=values["refresh_token"],
                    client_id=values["client_id"], redirect_uri=values["redirect_uri"],
                )
    except IdentityIssuerUnavailable:
        raise HTTPException(503, "Identity issuer unavailable") from None
    except (OAuthGrantDenied, ValueError):
        raise HTTPException(400, "OAuth grant rejected") from None
    return JSONResponse(
        result, headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
    )
