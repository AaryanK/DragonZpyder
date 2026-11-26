"""Native pending-account recovery, independently gated and operator scoped.

A recovered credential is recorded as proof, never an activation or session.
Delivery uses explicitly configured transactional SMTP over verified TLS.
No user-supplied URL, recipient override, credential logging or agent tool.
"""
from __future__ import annotations
import asyncio
import logging
import os
import re
import secrets
import smtplib
import ssl
from email.message import EmailMessage
from uuid import uuid4

import asyncpg
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from .http_bridge import _identity_db
from .pending_proof_http import _proof_enabled, _payload, _receipt
from .passwords import normalize_email, validate_password, hash_password, EmailAddressError, PasswordPolicyError
from .grants import _secret_digest

router = APIRouter(prefix="/identity/v1/import-proof/recovery", tags=["identity-recovery"])
_LOG = logging.getLogger(__name__)


def _enabled(request):
    _proof_enabled(request)
    if os.getenv("DRAGONZPYDER_NATIVE_PENDING_RECOVERY_ENABLED") != "1":
        raise HTTPException(404, "Not found")


def _smtp_settings():
    host=os.getenv("DRAGONZPYDER_RECOVERY_SMTP_HOST","")
    sender=os.getenv("DRAGONZPYDER_RECOVERY_SMTP_FROM","")
    username=os.getenv("DRAGONZPYDER_RECOVERY_SMTP_USERNAME","")
    password=os.getenv("DRAGONZPYDER_RECOVERY_SMTP_PASSWORD","")
    if not re.fullmatch(r"[A-Za-z0-9.-]{1,253}",host) or not username or not password:
        raise RuntimeError("Recovery delivery unavailable")
    return host,normalize_email(sender),username,password


def _deliver(recipient, token):
    host,sender,username,password=_smtp_settings()
    message=EmailMessage()
    message["From"]=sender
    message["To"]=normalize_email(recipient)
    message["Subject"]="DragonZpyder account recovery"
    message.set_content("Use this one-time code in the DragonZpyder account recovery form. "
                        "It expires in 20 minutes. If you did not request it, ignore this email.\n\n"+token)
    with smtplib.SMTP_SSL(host,465,timeout=8,context=ssl.create_default_context()) as smtp:
        smtp.login(username,password)
        smtp.send_message(message)


async def _global_budget(conn, purpose):
    digest=_secret_digest("pending-recovery-budget:"+purpose)
    count=await conn.fetchval("""
        INSERT INTO identity_login_rate_limits(identity_digest,attempt_count,window_started_at)
        VALUES($1,1,now()) ON CONFLICT(identity_digest) DO UPDATE
        SET attempt_count=CASE WHEN identity_login_rate_limits.window_started_at<now()-interval '15 minutes'
          THEN 1 ELSE identity_login_rate_limits.attempt_count+1 END,
        window_started_at=CASE WHEN identity_login_rate_limits.window_started_at<now()-interval '15 minutes'
          THEN now() ELSE identity_login_rate_limits.window_started_at END
        RETURNING attempt_count
    """,digest)
    if not isinstance(count,int) or count>120:
        raise HTTPException(429,"Try again later")


@router.post("/start",include_in_schema=False)
async def start_recovery(request:Request):
    _enabled(request)
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
            await _global_budget(db,"issue")
            recipient=await db.fetchval("SELECT public.issue_pending_recovery($1,$2)",email,
                                       _secret_digest("pending-recovery:"+token))
        if recipient is not None:
            try:
                await asyncio.to_thread(_deliver,recipient,token)
            except Exception:
                # No recipient, message, credential or exception text in logs.
                _LOG.warning("pending_recovery_delivery_failed")
    except asyncpg.PostgresError:
        raise HTTPException(503,"Recovery unavailable") from None
    return JSONResponse({"status":"if_eligible_sent"},status_code=202,headers={"Cache-Control":"no-store"})


@router.post("/complete",include_in_schema=False)
async def complete_recovery(request:Request):
    _enabled(request)
    body=await _payload(request,{"email":320,"code":43,"password":1024})
    try:
        email=normalize_email(body["email"])
        validate_password(body["password"],email=email)
        if not re.fullmatch(r"[A-Za-z0-9_-]{43}",body["code"]):
            raise ValueError("Invalid code")
    except (EmailAddressError,PasswordPolicyError,ValueError,UnicodeError):
        raise HTTPException(400,"Invalid code or password; use at least 12 characters and a strong password") from None
    proof=uuid4()
    try:
        async with _identity_db() as db:
            await _global_budget(db,"redeem")
            # Rate budget commits before expensive password hashing.
            hashed=await asyncio.to_thread(hash_password,body["password"])
            redeemed=await db.fetchval("SELECT public.redeem_pending_recovery($1,$2,$3,$4)",
                email,_secret_digest("pending-recovery:"+body["code"]),hashed,proof)
    except asyncpg.PostgresError:
        raise HTTPException(503,"Recovery unavailable") from None
    if redeemed is not True:
        raise HTTPException(401,"Recovery rejected")
    return _receipt(proof)
