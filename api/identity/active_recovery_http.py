"""Native active recovery. Separate purpose, schema and gates from pending proofs."""
import asyncio
import logging
import os
import re
import secrets
import asyncpg
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from .http_bridge import _enabled, _issuer, _identity_db
from .native_recovery_http import _smtp_settings, _deliver, _global_budget
from .pending_proof_http import _payload
from .grants import _secret_digest
from .passwords import normalize_email, validate_password, hash_password, EmailAddressError, PasswordPolicyError

router=APIRouter(prefix="/identity/v1/recovery",tags=["identity-active-recovery"])
_LOG=logging.getLogger(__name__)

def _gate(request):
    _enabled()
    if os.getenv("DRAGONZPYDER_ACTIVE_RECOVERY_ENABLED")!="1":
        raise HTTPException(404,"Not found")
    if request.headers.get("origin")!=_issuer():
        raise HTTPException(403,"Origin rejected")

@router.post("/start",include_in_schema=False)
async def start(request:Request):
    _gate(request)
    body=await _payload(request,{"email":320})
    try:
        email=normalize_email(body["email"])
    except EmailAddressError:
        raise HTTPException(400,"Invalid recovery request") from None
    try:
        _smtp_settings()
    except (RuntimeError,EmailAddressError):
        raise HTTPException(503,"Recovery delivery unavailable") from None
    token=secrets.token_urlsafe(32)
    try:
        async with _identity_db() as db:
            await _global_budget(db,"active-issue")
            recipient=await db.fetchval("SELECT public.issue_active_recovery($1,$2)",email,
                _secret_digest("active-recovery:"+token))
        if recipient:
            try:
                await asyncio.to_thread(_deliver,recipient,token)
            except Exception:
                _LOG.warning("active_recovery_delivery_failed")
    except asyncpg.PostgresError:
        raise HTTPException(503,"Recovery unavailable") from None
    return JSONResponse({"status":"if_eligible_sent"},status_code=202,headers={"Cache-Control":"no-store"})

@router.post("/complete",include_in_schema=False)
async def complete(request:Request):
    _gate(request)
    body=await _payload(request,{"email":320,"code":43,"password":1024})
    try:
        email=normalize_email(body["email"])
        validate_password(body["password"],email=email)
        if not re.fullmatch(r"[A-Za-z0-9_-]{43}",body["code"]):
            raise ValueError("Invalid code")
    except (EmailAddressError,PasswordPolicyError,ValueError,UnicodeError):
        raise HTTPException(400,"Invalid code or password; use a strong password") from None
    try:
        async with _identity_db() as db:
            await _global_budget(db,"active-redeem")
            hashed=await asyncio.to_thread(hash_password,body["password"])
            ok=await db.fetchval("SELECT public.redeem_active_recovery($1,$2,$3)",email,
                _secret_digest("active-recovery:"+body["code"]),hashed)
    except asyncpg.PostgresError:
        raise HTTPException(503,"Recovery unavailable") from None
    if ok is not True:
        raise HTTPException(401,"Recovery rejected")
    result=JSONResponse({"status":"password_reset"},headers={"Cache-Control":"no-store"})
    result.delete_cookie("__Host-dz_identity",secure=True,httponly=True,samesite="lax",path="/")
    result.delete_cookie("__Host-dz_csrf",secure=True,httponly=False,samesite="lax",path="/")
    return result
