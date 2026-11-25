"""First-party native audio-only WebRTC transport; no embedded provider key.

This opt-in gateway does not grant agent tools. Start reservations are durable
and ambiguous provider outcomes are never automatically retried.
"""
from __future__ import annotations
import asyncio
import hashlib
import json
import os
import re
from urllib.parse import urlsplit
from uuid import UUID
import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from .first_party_chat import _owner, _conversation_db

router = APIRouter(prefix="/v2/personal/voice", tags=["native-voice"])
_CALLS = "https://api.openai.com/v1/realtime/calls"


class VoiceOffer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: UUID
    sdp: str = Field(min_length=20, max_length=65536)


def voice_enabled():
    return os.getenv("DRAGONZPYDER_NATIVE_VOICE_ENABLED")=="1" and bool(os.getenv("DRAGONZPYDER_NATIVE_VOICE_API_KEY"))


def _key():
    if not voice_enabled():
        raise HTTPException(503, "Native realtime voice is disabled")
    return os.environ["DRAGONZPYDER_NATIVE_VOICE_API_KEY"]


def _call_id(location: str):
    p=urlsplit(location)
    if p.netloc and (p.scheme!="https" or p.netloc!="api.openai.com"):
        raise ValueError("Unexpected call location")
    match=re.fullmatch(r"/v1/realtime/calls/([A-Za-z0-9_-]{1,180})",p.path)
    if not match or p.query or p.fragment:
        raise ValueError("Invalid provider call location")
    return match.group(1)


def _audio_offer(sdp):
    return (sdp.startswith("v=0") and "\nm=audio " in sdp and "\nm=video " not in sdp
            and "\x00" not in sdp and len(sdp.encode("utf-8"))<=65536)


async def _hangup(client, key, call_id):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,180}",call_id or ""):
        return False
    try:
        result=await client.post(_CALLS+"/"+call_id+"/hangup",
                                 headers={"Authorization":"Bearer "+key},timeout=15)
        return result.status_code in (200,204,404)
    except httpx.HTTPError:
        return False


@router.post("/start")
async def start(payload: VoiceOffer, request: Request):
    owner=await _owner(request,changing=True)
    key=_key()
    if not _audio_offer(payload.sdp):
        raise HTTPException(422,"Invalid audio-only SDP offer")
    minutes=max(1,min(10,int(os.getenv("DRAGONZPYDER_NATIVE_VOICE_MINUTES","5"))))
    daily=max(1,min(10,int(os.getenv("DRAGONZPYDER_NATIVE_VOICE_DAILY_SESSIONS","3"))))
    async with _conversation_db() as db:
        async with db.transaction():
            await db.execute("SELECT pg_advisory_xact_lock(hashtextextended($1,0))","dz-native-voice:"+owner)
            count=await db.fetchval("""SELECT count(*) FROM dz_native_voice_sessions
               WHERE owner_id=$1 AND created_at>=date_trunc('day',now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'""",owner)
            active=await db.fetchval("""SELECT EXISTS(SELECT 1 FROM dz_native_voice_sessions
               WHERE owner_id=$1 AND state IN ('starting','active','unknown'))""",owner)
            if active or count>=daily:
                raise HTTPException(429,"Voice allowance or unresolved session limit reached")
            reserved=await db.fetchval("""INSERT INTO dz_native_voice_sessions
                (owner_id,session_id,state,expires_at) VALUES($1,$2,'starting',now()+$3*interval '1 minute')
                ON CONFLICT DO NOTHING RETURNING session_id""",owner,payload.session_id,minutes)
            if reserved is None:
                raise HTTPException(409,"Voice request already used")
    session={"type":"realtime","model":os.getenv("DRAGONZPYDER_NATIVE_VOICE_MODEL","gpt-realtime-2.1"),
             "instructions":"You are DragonZpyder's live voice companion. Speak naturally. You have no execution tools in this voice session; never claim to have performed an external action.",
             "audio":{"input":{"turn_detection":{"type":"server_vad","create_response":True,"interrupt_response":True},
                               "transcription":{"model":"gpt-4o-mini-transcribe"}},
                      "output":{"voice":"marin"}},"tools":[]}
    client=request.app.state.http
    call_id=None
    try:
        provider=await client.post(_CALLS,files={"sdp":(None,payload.sdp),"session":(None,json.dumps(session),"application/json")},
                                   headers={"Authorization":"Bearer "+key,"OpenAI-Safety-Identifier":hashlib.sha256(owner.encode()).hexdigest()[:32]},
                                   timeout=30)
        if provider.status_code not in (200,201):
            # Explicit 4xx rejection is not a successful session.
            if 400<=provider.status_code<500:
                async with _conversation_db() as db:
                    await db.execute("UPDATE dz_native_voice_sessions SET state='closed',updated_at=now() WHERE owner_id=$1 AND session_id=$2",owner,payload.session_id)
                raise HTTPException(502,"Voice provider rejected the session")
            raise RuntimeError("Uncertain upstream response")
        call_id=_call_id(provider.headers.get("location",""))
        answer=provider.text
        if not _audio_offer(answer):
            raise ValueError("Invalid SDP answer")
        async with _conversation_db() as db:
            expiry=await db.fetchval("""UPDATE dz_native_voice_sessions SET provider_call_id=$3,state='active',updated_at=now()
                WHERE owner_id=$1 AND session_id=$2 AND state='starting' RETURNING expires_at""",owner,payload.session_id,call_id)
        if expiry is None:
            raise RuntimeError("Voice reservation lost")
        return {"session_id":str(payload.session_id),"sdp":answer,"expires_at":expiry.isoformat(),"duration_seconds":minutes*60}
    except HTTPException:
        raise
    except Exception:
        closed=bool(call_id and await _hangup(client,key,call_id))
        async with _conversation_db() as db:
            await db.execute("""UPDATE dz_native_voice_sessions SET state=$3,provider_call_id=$4,updated_at=now()
                WHERE owner_id=$1 AND session_id=$2""",owner,payload.session_id,"closed" if closed else "unknown",call_id)
        raise HTTPException(503,"Voice setup outcome unconfirmed; do not automatically retry") from None


@router.post("/{session_id}/end")
async def end(session_id: UUID, request: Request):
    owner=await _owner(request,changing=True)
    key=_key()
    async with _conversation_db() as db:
        async with db.transaction():
            row=await db.fetchrow("SELECT state,provider_call_id FROM dz_native_voice_sessions WHERE owner_id=$1 AND session_id=$2 FOR UPDATE",owner,session_id)
            if row is None:
                raise HTTPException(404,"Voice session not found")
            if row["state"]=="closed":
                return {"session_id":str(session_id),"state":"closed"}
            if not row["provider_call_id"] or not await _hangup(request.app.state.http,key,row["provider_call_id"]):
                raise HTTPException(503,"Provider hangup not confirmed")
            await db.execute("UPDATE dz_native_voice_sessions SET state='closed',updated_at=now() WHERE owner_id=$1 AND session_id=$2",owner,session_id)
    return {"session_id":str(session_id),"state":"closed"}


async def cleanup_expired_voice(client):
    """Reconcile expired calls from PostgreSQL on every API replica/start."""
    while True:
        try:
            if voice_enabled():
                async with _conversation_db() as db:
                    async with db.transaction():
                        rows=await db.fetch("""SELECT owner_id,session_id,provider_call_id FROM dz_native_voice_sessions
                           WHERE state IN ('active','unknown') AND provider_call_id IS NOT NULL AND expires_at<=now()
                           ORDER BY expires_at LIMIT 5 FOR UPDATE SKIP LOCKED""")
                        for row in rows:
                            if await _hangup(client,_key(),row["provider_call_id"]):
                                await db.execute("UPDATE dz_native_voice_sessions SET state='closed',updated_at=now() WHERE owner_id=$1 AND session_id=$2",row["owner_id"],row["session_id"])
        except asyncio.CancelledError:
            raise
        except Exception:
            # Fail closed: unresolved reservations continue blocking new calls.
            pass
        await asyncio.sleep(15)
