"""First-party native browser login; no provider secrets or session tokens in links."""
import base64
import hashlib
import os
import re
import secrets
from urllib.parse import urlencode
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
import httpx

from .http_bridge import _enabled, _identity_db
from .provider_http import _origin_check, _success
from .grants import _secret_digest
from .providers import ProviderProofDenied, exchange_discord_oauth_code, verify_google_identity_token, find_login_account
from .native_signup import register_native_google_account
from .sessions import create_browser_session, SessionDenied

router=APIRouter(prefix="/identity/v1/mobile",tags=["identity-mobile"])
PUBLIC="https://dragonzpyder.xyz"
HEADERS={"Cache-Control":"no-store","Referrer-Policy":"no-referrer"}
TOKEN=r"[A-Za-z0-9_-]{43,128}"


def config(provider):
    if provider not in ("google","discord"):
        raise HTTPException(404,"Provider not supported")
    prefix="DRAGONZPYDER_IDENTITY_"+provider.upper()
    redirect=PUBLIC+"/dz/identity/v1/mobile/"+provider+"/callback"
    client=os.getenv(prefix+"_CLIENT_ID","").strip()
    secret=os.getenv(prefix+"_CLIENT_SECRET","")
    if not client or not secret or os.getenv(prefix+"_MOBILE_REDIRECT_URI")!=redirect:
        raise HTTPException(503,"Mobile "+provider+" OAuth not configured")
    return client,secret,redirect


def gate():
    _enabled()
    if os.getenv("DRAGONZPYDER_IDENTITY_MOBILE_OAUTH_ENABLED")!="1":
        raise HTTPException(404,"Mobile OAuth unavailable")


def digest(label,value):
    return _secret_digest("mobile:"+label+":"+value)


def pkce(verifier):
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).decode().rstrip("=")


async def claim_callback(db,provider,state,binding):
    if not re.fullmatch(TOKEN,state) or not re.fullmatch(TOKEN,binding):
        return None
    return await db.fetchrow("""UPDATE identity_mobile_provider_attempts SET callback_claimed_at=now()
        WHERE state_hash=$1 AND browser_hash=$2 AND provider=$3 AND expires_at>now()
        AND callback_claimed_at IS NULL RETURNING app_state,nonce,register""",
        digest("state",state),digest("browser",binding),provider)


async def redeem_ticket(db,provider,ticket,verifier):
    return await db.fetchval("""UPDATE identity_mobile_provider_attempts SET redeemed_at=now()
        WHERE ticket_hash=$1 AND challenge=$2 AND provider=$3
        AND callback_claimed_at IS NOT NULL AND redeemed_at IS NULL AND expires_at>now()
        RETURNING subject""",digest("ticket",ticket),pkce(verifier),provider)


@router.get("/{provider}/start",include_in_schema=False)
async def start(provider:str,request:Request,state:str="",code_challenge:str="",register:bool=False):
    gate()
    client,_,redirect=config(provider)
    if not re.fullmatch(TOKEN,state) or not re.fullmatch(r"[A-Za-z0-9_-]{43}",code_challenge):
        raise HTTPException(400,"S256 device proof required")
    if register and provider!="google":
        raise HTTPException(400,"Discord login requires an existing linked account")
    provider_state=secrets.token_urlsafe(40)
    binding=secrets.token_urlsafe(40)
    nonce=secrets.token_urlsafe(32)
    async with _identity_db() as db:
        async with db.transaction():
            # Serialize starts and bound outstanding global challenges. No raw IP
            # or provider credentials are persisted.
            await db.execute("SELECT pg_advisory_xact_lock(hashtext('dz-mobile-login-start'))")
            await db.execute("DELETE FROM identity_mobile_provider_attempts WHERE expires_at<=now()")
            if await db.fetchval("SELECT count(*) FROM identity_mobile_provider_attempts")>=10000:
                raise HTTPException(429,"Sign-in temporarily busy")
            await db.execute("""INSERT INTO identity_mobile_provider_attempts
                (state_hash,app_state,browser_hash,challenge,provider,nonce,register,expires_at)
                VALUES($1,$2,$3,$4,$5,$6,$7,now()+interval '5 minutes')""",
                digest("state",provider_state),state,digest("browser",binding),code_challenge,provider,nonce,register)
    params={"client_id":client,"redirect_uri":redirect,"response_type":"code","state":provider_state}
    if provider=="google":
        url="https://accounts.google.com/o/oauth2/v2/auth"
        params.update(scope="openid email profile",nonce=nonce,prompt="select_account")
    else:
        url="https://discord.com/oauth2/authorize"
        params.update(scope="identify")
    response=RedirectResponse(url+"?"+urlencode(params),status_code=303,headers=HEADERS)
    response.set_cookie("__Host-dz_mobile_provider",binding,secure=True,httponly=True,samesite="lax",path="/",max_age=300)
    return response


async def google_proof(client,code,nonce):
    app,secret,redirect=config("google")
    response=await client.post("https://oauth2.googleapis.com/token",data={"client_id":app,
        "client_secret":secret,"code":code,"redirect_uri":redirect,"grant_type":"authorization_code"},timeout=10,follow_redirects=False)
    response.raise_for_status()
    token=response.json().get("id_token")
    if not isinstance(token,str):
        raise ProviderProofDenied("Google token absent")
    import asyncio
    return await asyncio.to_thread(verify_google_identity_token,token,expected_nonce=nonce)


@router.get("/{provider}/callback",include_in_schema=False)
async def callback(provider:str,request:Request,state:str="",code:str="",error:str=""):
    gate()
    _,_,redirect=config(provider)
    async with _identity_db() as db:
        row=await claim_callback(db,provider,state,request.cookies.get("__Host-dz_mobile_provider",""))
    if row is None:
        raise HTTPException(400,"Mobile sign-in expired or invalid")
    try:
        if error or not 8<=len(code)<=2048:
            raise ProviderProofDenied("Provider sign-in denied")
        async with httpx.AsyncClient() as client:
            proof=await google_proof(client,code,row["nonce"]) if provider=="google" else await exchange_discord_oauth_code(client,code=code,redirect_uri=redirect,mobile=True)
        async with _identity_db() as db:
            subject=await register_native_google_account(db,proof) if row["register"] else await find_login_account(db,proof)
            ticket=secrets.token_urlsafe(40)
            changed=await db.execute("""UPDATE identity_mobile_provider_attempts SET ticket_hash=$1,subject=$2,
                expires_at=LEAST(expires_at,now()+interval '90 seconds')
                WHERE state_hash=$3 AND callback_claimed_at IS NOT NULL AND ticket_hash IS NULL AND expires_at>now()""",
                digest("ticket",ticket),subject,digest("state",state))
            if changed!="UPDATE 1":
                raise ProviderProofDenied("Login challenge expired")
        params={"state":row["app_state"],"ticket":ticket}
    except (ProviderProofDenied,httpx.HTTPError,ValueError,TypeError):
        params={"state":row["app_state"],"error":"provider_rejected"}
    response=RedirectResponse("dragonzpyder://auth/"+provider+"?"+urlencode(params),status_code=303,headers=HEADERS)
    response.delete_cookie("__Host-dz_mobile_provider",secure=True,httponly=True,samesite="lax",path="/")
    return response


class Redeem(BaseModel):
    ticket:str=Field(pattern=TOKEN,min_length=43,max_length=128)
    verifier:str=Field(pattern=TOKEN,min_length=43,max_length=128)


@router.post("/{provider}/redeem",include_in_schema=False)
async def redeem(provider:str,payload:Redeem,request:Request):
    gate()
    config(provider)
    _origin_check(request)
    try:
        async with _identity_db() as db:
            async with db.transaction():
                subject=await redeem_ticket(db,provider,payload.ticket,payload.verifier)
                if not subject:
                    raise ProviderProofDenied("Invalid mobile ticket")
                session=await create_browser_session(db,authenticated_subject=subject)
    except (ProviderProofDenied,SessionDenied):
        raise HTTPException(401,"Mobile authentication rejected") from None
    return _success(session)


@router.get("/capabilities",include_in_schema=False)
async def capabilities():
    gate()
    result={}
    for provider in ("google","discord"):
        try:
            config(provider)
            result[provider]=True
        except HTTPException:
            result[provider]=False
    return result
