"""LiveKit audio transport admission for the canonical Personal harness.

No user bearer credential is transferred to the voice worker. A private
room-scoped nonce and a dedicated service token authorize transcript delivery;
the original first-party session is rechecked before each execution.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime,timedelta,timezone
import hashlib
import hmac
import json
import os
import re
import secrets
from urllib.parse import urlsplit
from uuid import UUID,uuid5

from fastapi import APIRouter,HTTPException,Request
from pydantic import BaseModel,ConfigDict,Field
from .first_party_chat import _owner,_conversation_db,_require_conversation,_chat_owned,ChatInput,_fingerprint
from .native_workflows import session_reference,verify_authority

router=APIRouter(tags=["modular-live-voice"])
AGENT_NAME="dragonzpyder-voice-transport"
ROOM_PREFIX="dz-voice-"


class Offer(BaseModel):
    model_config=ConfigDict(extra="forbid")
    session_id:UUID
    conversation_id:UUID|None=None
    mcp_connection_ids:list[str]=Field(default_factory=list,max_length=10)


class WorkerScope(BaseModel):
    model_config=ConfigDict(extra="forbid")
    session_id:UUID
    room:str=Field(pattern=r"^dz-voice-[a-f0-9]{32}$")
    nonce:str=Field(pattern=r"^[A-Za-z0-9_-]{43,86}$")


class WorkerTurn(WorkerScope):
    event_id:str=Field(pattern=r"^[A-Za-z0-9_-]{1,180}$")
    transcript:str=Field(min_length=1,max_length=12000)


def config():
    url=os.getenv("LIVEKIT_URL","")
    parsed=urlsplit(url)
    if (parsed.scheme!="wss" or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path not in ("","/")):
        raise ValueError("Explicit secure LiveKit URL required")
    key=os.getenv("LIVEKIT_API_KEY","")
    secret=os.getenv("LIVEKIT_API_SECRET","")
    token=os.getenv("DRAGONZPYDER_VOICE_WORKER_TOKEN","")
    if not key or len(secret)<24 or len(token)<40:
        raise ValueError("Dedicated voice transport credentials required")
    duration=int(os.getenv("DRAGONZPYDER_MODULAR_VOICE_SECONDS","300"))
    global_active=int(os.getenv("DRAGONZPYDER_MODULAR_VOICE_GLOBAL_ACTIVE","2"))
    daily=int(os.getenv("DRAGONZPYDER_MODULAR_VOICE_DAILY_SESSIONS","3"))
    global_daily=int(os.getenv("DRAGONZPYDER_MODULAR_VOICE_GLOBAL_DAILY_SESSIONS","12"))
    if not 30<=duration<=600 or not 1<=global_active<=16 or not 1<=daily<=10 or not daily<=global_daily<=100:
        raise ValueError("Voice admission policy out of bounds")
    return url,key,secret,token,duration,global_active,daily,global_daily


def enabled():
    if not all(os.getenv(x)=="1" for x in (
            "DRAGONZPYDER_MODULAR_VOICE_ENABLED","DRAGONZPYDER_FIRST_PARTY_CHAT_ENABLED",
            "DRAGONZPYDER_FIRST_PARTY_REQUEST_LEDGER_ENABLED","DRAGONZPYDER_AGENTS_ENABLED","DRAGONZPYDER_IDENTITY_HTTP_ENABLED")):
        return False
    try:
        config()
        return True
    except (ValueError,TypeError):
        return False


def room_name(session_id):
    return ROOM_PREFIX+session_id.hex


def nonce_digest(value):
    return hashlib.sha256(value.encode("ascii")).hexdigest()


@asynccontextmanager
async def livekit_api():
    from livekit import api
    url,key,secret,*_=config()
    async with api.LiveKitAPI(url=url,api_key=key,api_secret=secret,timeout=10) as client:
        yield client


def participant_token(session_id):
    from livekit import api
    url,key,secret,*_=config()
    # Token cannot publish video or data, create rooms, or administer users.
    # The room name and identity are fixed by the server, not the browser.
    return (api.AccessToken(key,secret).with_identity("user-"+session_id.hex)
            .with_ttl(timedelta(seconds=90)).with_grants(api.VideoGrants(
                room_join=True,room=room_name(session_id),can_publish=True,
                can_publish_sources=["microphone"],can_subscribe=True,
                can_publish_data=False,can_update_own_metadata=False)).to_jwt())


async def delete_room(room):
    from livekit import api
    if not re.fullmatch(r"dz-voice-[a-f0-9]{32}",room):
        return False
    try:
        async with livekit_api() as client:
            await client.room.delete_room(api.DeleteRoomRequest(room=room))
        return True
    except Exception:
        # An explicit confirmed absence is safe; other transport errors retain
        # the reservation for the expiry reconciliation loop.
        try:
            async with livekit_api() as client:
                rooms=await client.room.list_rooms(api.ListRoomsRequest(names=[room]))
            return not rooms.rooms
        except Exception:
            return False


@router.post("/v2/personal/voice/modular/start")
async def start(payload:Offer,request:Request):
    owner=await _owner(request,changing=True)
    if not enabled():raise HTTPException(503,"Modular voice unavailable")
    if (len(set(payload.mcp_connection_ids))!=len(payload.mcp_connection_ids)
            or any(not re.fullmatch(r"c[a-f0-9]{30}",x) for x in payload.mcp_connection_ids)):
        raise HTTPException(422,"Invalid voice account selection")
    url,_,_,_,duration,global_active,daily,global_daily=config()
    ref=session_reference(request)
    await verify_authority(owner,ref)
    nonce=secrets.token_urlsafe(32)
    room=room_name(payload.session_id)
    async with _conversation_db() as db:
        async with db.transaction():
            # Shared lock prevents concurrent sessions across API replicas.
            await db.execute("SELECT pg_advisory_xact_lock(hashtextextended($1,0))","dz-modular-voice-global")
            await db.execute("SELECT pg_advisory_xact_lock(hashtextextended($1,0))","dz-native-voice:"+owner)
            if payload.conversation_id:
                await _require_conversation(db,user=owner,conversation_id=payload.conversation_id)
            counts=await db.fetchrow("""SELECT
                count(*) FILTER(WHERE state IN ('starting','active','unknown') AND owner_id=$1) AS owner_active,
                count(*) FILTER(WHERE state IN ('starting','active','unknown') AND transport='modular') AS global_active,
                count(*) FILTER(WHERE owner_id=$1 AND created_at>=date_trunc('day',now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC') AS owner_daily,
                count(*) FILTER(WHERE transport='modular' AND created_at>=date_trunc('day',now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC') AS global_daily
                FROM dz_native_voice_sessions""",owner)
            if counts["owner_active"] or counts["global_active"]>=global_active or counts["owner_daily"]>=daily or counts["global_daily"]>=global_daily:
                raise HTTPException(429,"Voice session allowance reached")
            expiry=await db.fetchval("""INSERT INTO dz_native_voice_sessions
                (owner_id,session_id,state,expires_at,transport,agent_mode,conversation_id,mcp_connection_ids,
                 session_reference,room_name,worker_nonce_sha256)
                VALUES($1,$2,'starting',now()+$3*interval '1 second','modular',TRUE,$4,$5::jsonb,$6,$7,$8)
                ON CONFLICT DO NOTHING RETURNING expires_at""",owner,payload.session_id,duration,
                payload.conversation_id,json.dumps(payload.mcp_connection_ids),ref,room,nonce_digest(nonce))
            if expiry is None:raise HTTPException(409,"Voice session identity already used")
    try:
        from livekit import api
        async with livekit_api() as client:
            await client.room.create_room(api.CreateRoomRequest(name=room,empty_timeout=20,
                departure_timeout=10,max_participants=2))
            # Metadata is delivered only to the dispatched transport worker.
            await client.agent_dispatch.create_dispatch(api.CreateAgentDispatchRequest(
                agent_name=AGENT_NAME,room=room,metadata=json.dumps(
                    {"session_id":str(payload.session_id),"room":room,"nonce":nonce})))
        token=participant_token(payload.session_id)
        async with _conversation_db() as db:
            updated=await db.fetchval("""UPDATE dz_native_voice_sessions SET state='active',updated_at=now()
                WHERE owner_id=$1 AND session_id=$2 AND state='starting' RETURNING session_id""",
                owner,payload.session_id)
        if updated!=payload.session_id:raise RuntimeError("Reservation lost")
        return {"session_id":str(payload.session_id),"transport":"modular","server_url":url,
                "participant_token":token,"expires_at":expiry.isoformat(),"duration_seconds":duration}
    except Exception:
        closed=await delete_room(room)
        async with _conversation_db() as db:
            await db.execute("""UPDATE dz_native_voice_sessions SET state=$3,updated_at=now()
                WHERE owner_id=$1 AND session_id=$2 AND transport='modular'""",
                owner,payload.session_id,"closed" if closed else "unknown")
        raise HTTPException(503,"Voice setup unconfirmed; do not automatically retry") from None


async def worker_row(scope,request, *, starting=False):
    if not enabled():raise HTTPException(503,"Modular voice unavailable")
    token=config()[3]
    if not hmac.compare_digest(request.headers.get("authorization",""),"Bearer "+token):
        raise HTTPException(403,"Dedicated voice worker required")
    if scope.room!=room_name(scope.session_id):raise HTTPException(403,"Room mismatch")
    async with _conversation_db() as db:
        row=await db.fetchrow("""SELECT owner_id,session_reference,conversation_id,mcp_connection_ids,expires_at
            FROM dz_native_voice_sessions WHERE session_id=$1 AND room_name=$2 AND transport='modular'
            AND (state='active' OR ($4 AND state='starting')) AND expires_at>now() AND worker_nonce_sha256=$3""",
            scope.session_id,scope.room,nonce_digest(scope.nonce),starting)
    if row is None:raise HTTPException(403,"Voice scope unavailable")
    try:await verify_authority(row["owner_id"],row["session_reference"])
    except Exception:raise HTTPException(403,"Voice authority expired") from None
    return row


@router.post("/internal/agents/voice/modular/authorize")
async def authorize(scope:WorkerScope,request:Request):
    row=await worker_row(scope,request,starting=True)
    return {"expires_at":row["expires_at"].isoformat(),"participant_identity":"user-"+scope.session_id.hex}


@router.post("/internal/agents/voice/modular/turn")
async def turn(payload:WorkerTurn,request:Request):
    row=await worker_row(payload,request)
    owner=row["owner_id"]
    request_id=uuid5(payload.session_id,payload.event_id)
    async with _conversation_db() as db:
        key="dz-modular-voice-turn:"+str(payload.session_id)
        if not await db.fetchval("SELECT pg_try_advisory_lock(hashtextextended($1,0))",key):
            raise HTTPException(409,"Voice turn already processing")
        try:
            row=await worker_row(payload,request)
            choices=row["mcp_connection_ids"]
            if isinstance(choices,str):choices=json.loads(choices)
            prior=await db.fetchrow("""SELECT conversation_id,status,response,fingerprint
                FROM dz_first_party_chat_requests WHERE owner_id=$1 AND request_id=$2""",owner,request_id)
            if prior is not None:
                for cid in (None,prior["conversation_id"]):
                    candidate=ChatInput(message=payload.transcript,request_id=request_id,
                        conversation_id=cid,mcp_connection_ids=choices)
                    if _fingerprint(candidate)==prior["fingerprint"]:
                        if prior["status"]!="completed":raise HTTPException(409,"Prior voice turn unconfirmed")
                        result=prior["response"]
                        if isinstance(result,str):result=json.loads(result)
                        if not isinstance(result,dict):raise HTTPException(503,"Voice response unavailable")
                        break
                else:raise HTTPException(409,"Voice event identity conflict")
            else:
                async def reauthorize():
                    await worker_row(payload,request)
                result=await _chat_owned(ChatInput(message=payload.transcript,request_id=request_id,
                    conversation_id=row["conversation_id"],mcp_connection_ids=choices),request,owner,
                    authority=reauthorize)
            await db.execute("""UPDATE dz_native_voice_sessions SET conversation_id=$3,updated_at=now()
                WHERE owner_id=$1 AND session_id=$2 AND state='active'""",owner,payload.session_id,UUID(result["conversation_id"]))
            return result
        finally:
            await db.execute("SELECT pg_advisory_unlock(hashtextextended($1,0))",key)


@router.post("/v2/personal/voice/modular/{session_id}/end")
async def end(session_id:UUID,request:Request):
    owner=await _owner(request,changing=True)
    async with _conversation_db() as db:
        row=await db.fetchrow("""SELECT state,room_name FROM dz_native_voice_sessions
            WHERE owner_id=$1 AND session_id=$2 AND transport='modular'""",owner,session_id)
        if row is None:raise HTTPException(404,"Voice session not found")
        if row["state"]=="closed":return {"session_id":str(session_id),"state":"closed"}
        # Revoke execution authority before trying to disconnect audio.
        await db.execute("""UPDATE dz_native_voice_sessions SET state='unknown',updated_at=now()
            WHERE owner_id=$1 AND session_id=$2""",owner,session_id)
    if not await delete_room(row["room_name"]):raise HTTPException(503,"Voice hangup unconfirmed")
    async with _conversation_db() as db:
        await db.execute("""UPDATE dz_native_voice_sessions SET state='closed',updated_at=now()
            WHERE owner_id=$1 AND session_id=$2""",owner,session_id)
    return {"session_id":str(session_id),"state":"closed"}


async def cleanup_expired_modular():
    while True:
        try:
            if os.getenv("LIVEKIT_API_KEY"):
                async with _conversation_db() as db:
                    rows=await db.fetch("""SELECT owner_id,session_id,room_name FROM dz_native_voice_sessions
                        WHERE transport='modular' AND state IN ('starting','active','unknown') AND expires_at<=now()
                        ORDER BY expires_at LIMIT 5""")
                    for row in rows:
                        if await delete_room(row["room_name"]):
                            await db.execute("""UPDATE dz_native_voice_sessions SET state='closed',updated_at=now()
                                WHERE owner_id=$1 AND session_id=$2 AND expires_at<=now()""",row["owner_id"],row["session_id"])
        except asyncio.CancelledError:raise
        except Exception:pass
        await asyncio.sleep(15)
