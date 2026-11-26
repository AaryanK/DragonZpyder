"""No-public-activation password login HTTP adapter.

Production is expressly blocked until migration and auth security review.
"""
import hmac
import httpx

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from .http_bridge import _enabled, _identity_db, _issuer
from .password_login import password_login, LoginDenied
from .sessions import SessionDenied, revoke_browser_session, resolve_browser_session
from .profile_avatar import avatar_enabled, read_google_avatar, fetch_google_avatar

router = APIRouter(prefix="/identity/v1", tags=["identity-bridge"])


class PasswordLoginInput(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


def _origin_checked(request: Request) -> None:
    if request.headers.get("origin") != _issuer():
        raise HTTPException(403, "Origin rejected")


@router.post("/password/login", include_in_schema=False)
async def login_with_password(payload: PasswordLoginInput, request: Request):
    _enabled()
    _origin_checked(request)
    try:
        async with _identity_db() as conn:
            session = await password_login(conn, email=payload.email, password=payload.password)
    except LoginDenied:
        raise HTTPException(401, "Invalid credentials") from None
    response = JSONResponse({"authenticated": True}, headers={"Cache-Control": "no-store"})
    # Host-only __Host- cookies require Secure + Path=/ and no Domain.
    response.set_cookie("__Host-dz_identity", session.secret, secure=True, httponly=True,
                        samesite="lax", path="/", max_age=7 * 24 * 3600)
    response.set_cookie("__Host-dz_csrf", session.csrf, secure=True, httponly=False,
                        samesite="lax", path="/", max_age=7 * 24 * 3600)
    return response


@router.post("/logout", include_in_schema=False)
async def logout_identity(request: Request):
    _enabled()
    _origin_checked(request)
    secret = request.cookies.get("__Host-dz_identity", "")
    csrf = request.cookies.get("__Host-dz_csrf", "")
    submitted_csrf = request.headers.get("x-dz-csrf", "")
    if not csrf or not submitted_csrf or not hmac.compare_digest(csrf, submitted_csrf):
        raise HTTPException(403, "Invalid logout CSRF")
    if secret:
        try:
            async with _identity_db() as conn:
                await resolve_browser_session(conn, secret=secret, csrf=submitted_csrf, require_csrf=True)
                await revoke_browser_session(conn, secret=secret)
        except SessionDenied:
            raise HTTPException(403, "Invalid logout session") from None
    response = JSONResponse({"authenticated": False}, headers={"Cache-Control": "no-store"})
    response.delete_cookie("__Host-dz_identity", secure=True, httponly=True, samesite="lax", path="/")
    response.delete_cookie("__Host-dz_csrf", secure=True, httponly=False, samesite="lax", path="/")
    return response


class UpdateProfileInput(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)


@router.get("/me", include_in_schema=False)
async def native_profile(request: Request):
    _enabled()
    secret = request.cookies.get("__Host-dz_identity", "")
    try:
        async with _identity_db() as db:
            owner = await resolve_browser_session(db, secret=secret)
            row = await db.fetchrow(
                """SELECT subject, email, display_name, identity_origin
                   FROM identity_accounts
                   WHERE subject=$1 AND source_active=TRUE AND status='active'""",
                owner,
            )
            avatar = await read_google_avatar(db, owner) if row is not None else None
    except SessionDenied:
        raise HTTPException(401, "Active first-party session required") from None
    if row is None:
        raise HTTPException(401, "Active account required")
    return {"id": row["subject"], "email": row["email"],
            "display_name": row["display_name"],
            "identity_origin": row["identity_origin"],
            **({"avatar_available": True} if avatar else {})}


@router.get("/avatar", include_in_schema=False)
async def native_avatar(request: Request):
    """Return only the current session owner\x27s verified Google image."""
    _enabled()
    if not avatar_enabled():
        raise HTTPException(404, "Avatar unavailable")
    try:
        async with _identity_db() as db:
            owner = await resolve_browser_session(db, secret=request.cookies.get("__Host-dz_identity", ""))
            picture = await read_google_avatar(db, owner)
    except SessionDenied:
        raise HTTPException(401, "Active first-party session required") from None
    if not picture:
        raise HTTPException(404, "Avatar unavailable")
    # Isolated client: no user cookies, authorization header or environment proxy.
    async with httpx.AsyncClient(timeout=5.0, trust_env=False, follow_redirects=False) as client:
        image = await fetch_google_avatar(client, picture)
    if not image:
        raise HTTPException(404, "Avatar unavailable")
    mime, data = image
    return Response(data, media_type=mime, headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff", "Cross-Origin-Resource-Policy": "same-origin"})


@router.patch("/me", include_in_schema=False)
async def native_profile_update(payload: UpdateProfileInput, request: Request):
    _enabled()
    _origin_checked(request)
    secret = request.cookies.get("__Host-dz_identity", "")
    csrf = request.headers.get("x-dz-csrf", "")
    try:
        async with _identity_db() as db:
            owner = await resolve_browser_session(
                db, secret=secret, csrf=csrf, require_csrf=True)
            value = payload.display_name.strip()
            if not value:
                raise HTTPException(422, "Display name cannot be blank")
            updated = await db.execute(
                """UPDATE identity_accounts SET display_name=$1
                   WHERE subject=$2 AND status='active' AND source_active=TRUE""",
                value, owner,
            )
            if updated != "UPDATE 1":
                raise HTTPException(401, "Active account required")
    except SessionDenied:
        raise HTTPException(401, "Active first-party session required") from None
    return {"updated": True}
