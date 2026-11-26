"""Browser-native utterance voice. OpenRouter is the only inference account.

No LiveKit or Deepgram service is required. The provider gateway retains the
existing capped media key, rate limits and audit. Audio is not stored; only
canonical chat transcripts, request receipts and irreversible attempt fences.
"""
from __future__ import annotations
import base64
import hashlib
import io
import json
import os
import re
import struct
import wave
from uuid import UUID,uuid5

from fastapi import APIRouter,HTTPException,Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel,ConfigDict,Field
from .first_party_chat import _owner,_conversation_db,_require_conversation,_chat_owned,ChatInput
from .native_workflows import session_reference,verify_authority
from .modular_voice import Offer

router=APIRouter(tags=["openrouter-voice"])
STT="openai/whisper-large-v3-turbo"
TTS="hexgrad/kokoro-82m"
VOICE="af_alloy"
MAX_WAV=960044
MAX_TURNS=20
MAX_SEGMENTS=4
MAX_CHARS=900

def enabled():
    return (all(os.getenv(key)=="1" for key in ("DRAGONZPYDER_OPENROUTER_VOICE_ENABLED",
        "DRAGONZPYDER_FIRST_PARTY_CHAT_ENABLED","DRAGONZPYDER_FIRST_PARTY_REQUEST_LEDGER_ENABLED",
        "DRAGONZPYDER_AGENTS_ENABLED","DRAGONZPYDER_IDENTITY_HTTP_ENABLED"))
        and len(os.getenv("DRAGONZPYDER_AGENT_MEDIA_OPENROUTER_API_KEY",""))>=20)

class Utterance(BaseModel):
    model_config=ConfigDict(extra="forbid")
    event_id:UUID
    audio:str=Field(min_length=60,max_length=1280060)

def decode_wav(encoded):
    try:
        raw=base64.b64decode(encoded,validate=True)
        # Require the simple canonical 44-byte PCM WAV header our clients emit.
        if not 44<len(raw)<=MAX_WAV or raw[:4]!=b"RIFF" or raw[8:16]!=b"WAVEfmt " or raw[36:40]!=b"data":
            raise ValueError()
        if struct.unpack_from("<I",raw,4)[0]!=len(raw)-8 or struct.unpack_from("<I",raw,40)[0]!=len(raw)-44:
            raise ValueError()
        if struct.unpack_from("<IHHIIHH",raw,16)!=(16,1,1,16000,32000,2,16):
            raise ValueError()
        with wave.open(io.BytesIO(raw),"rb") as wav:
            if not 2400<=wav.getnframes()<=480000 or wav.getnframes()*2!=len(raw)-44:
                raise ValueError()
        return raw
    except (ValueError,EOFError,wave.Error,struct.error,TypeError):
        raise ValueError("Invalid bounded mono PCM WAV") from None

def segments(answer):
    # Use only the committed canonical answer. Do not accept arbitrary speech
    # text from the client. Limit total speech; the complete answer stays in chat.
    remaining=" ".join(answer.split())
    out=[]
    for i in range(MAX_SEGMENTS):
        if not remaining:break
        limit=300 if i==0 else MAX_CHARS
        if len(remaining)<=limit:
            out.append(remaining);remaining="";break
        cut=max(remaining.rfind(x,0,limit) for x in (". ","? ","! ","; "))
        if cut<40:cut=remaining.rfind(" ",0,limit)
        if cut<1:cut=limit-1
        out.append(remaining[:cut+1].strip())
        remaining=remaining[cut+1:].strip()
    if remaining and len(out)==MAX_SEGMENTS:
        suffix=" The rest of the answer is in chat."
        out[-1]=out[-1][:MAX_CHARS-len(suffix)].rstrip()+suffix
    return out

def validate_voice_payload(path,body):
    if path=="/audio/transcriptions":
        if set(body)!={"model","input_audio"} or body["model"]!=STT or set(body["input_audio"])!={"data","format"} or body["input_audio"]["format"]!="wav":
            raise ValueError("Unapproved voice STT")
        decode_wav(body["input_audio"]["data"])
    elif path=="/audio/speech":
        if set(body)!={"model","input","voice","response_format"} or body["model"]!=TTS or body["voice"]!=VOICE or body["response_format"]!="mp3":
            raise ValueError("Unapproved voice TTS")
        if not isinstance(body["input"],str) or not 1<=len(body["input"].strip())<=MAX_CHARS:
            raise ValueError("Voice text exceeds bound")
    else:raise ValueError("Unsupported voice operation")

async def gateway(request,path,payload):
    from provider_gateway import provider_request
    validate_voice_payload(path,payload)
    response=await provider_request(request,path,app_id="agent-voice",runtime=request.app.state.provider_runtime,voice_payload=payload)
    if response.status_code!=200 or response.headers.get("x-dragonzpyder-audit")!="persisted":
        raise HTTPException(503,"Speech provider or capped budget unavailable; do not replay")
    return response

async def authority(owner,session_id):
    if not enabled():raise HTTPException(503,"OpenRouter voice unavailable")
    async with _conversation_db() as db:
        row=await db.fetchrow("""SELECT session_reference,conversation_id,mcp_connection_ids
            FROM dz_native_voice_sessions WHERE owner_id=$1 AND session_id=$2
            AND transport='openrouter' AND state='active' AND expires_at>now()""",owner,session_id)
    if row is None:raise HTTPException(403,"Voice session expired or closed")
    try:await verify_authority(owner,row["session_reference"])
    except Exception:raise HTTPException(403,"Voice authority revoked") from None
    return row

@router.post("/v2/personal/voice/openrouter/start")
async def start(payload:Offer,request:Request):
    owner=await _owner(request,changing=True)
    if not enabled():raise HTTPException(503,"OpenRouter voice unavailable")
    if len(set(payload.mcp_connection_ids))!=len(payload.mcp_connection_ids) or any(not re.fullmatch(r"c[a-f0-9]{30}",x) for x in payload.mcp_connection_ids):
        raise HTTPException(422,"Invalid voice account selection")
    from .key_budget import verify_key_budget
    from usage_ledger import ledger
    budget=await verify_key_budget(request.app.state.http,os.environ["DRAGONZPYDER_AGENT_MEDIA_OPENROUTER_API_KEY"])
    if budget.get("approved") is not True or not ledger.available:
        raise HTTPException(503,"Capped OpenRouter speech budget or accounting unavailable")
    ref=session_reference(request)
    await verify_authority(owner,ref)
    async with _conversation_db() as db:
        async with db.transaction():
            await db.execute("SELECT pg_advisory_xact_lock(hashtextextended($1,0))","dz-modular-voice-global")
            await db.execute("SELECT pg_advisory_xact_lock(hashtextextended($1,0))","dz-native-voice:"+owner)
            if payload.conversation_id:await _require_conversation(db,user=owner,conversation_id=payload.conversation_id)
            await db.execute("""UPDATE dz_native_voice_sessions SET state='closed'
                WHERE transport='openrouter' AND state='active' AND expires_at<=now()""")
            counts=await db.fetchrow("""SELECT
                count(*) FILTER(WHERE state IN ('starting','active','unknown') AND owner_id=$1) AS active,
                count(*) FILTER(WHERE state='active' AND transport='openrouter') AS global_active,
                count(*) FILTER(WHERE owner_id=$1 AND created_at>=date_trunc('day',now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC') AS daily,
                count(*) FILTER(WHERE transport='openrouter' AND created_at>=date_trunc('day',now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC') AS global_daily
                FROM dz_native_voice_sessions""",owner)
            if counts["active"] or counts["global_active"]>=2 or counts["daily"]>=3 or counts["global_daily"]>=12:
                raise HTTPException(429,"Voice session allowance reached")
            expiry=await db.fetchval("""INSERT INTO dz_native_voice_sessions
                (owner_id,session_id,state,expires_at,transport,agent_mode,conversation_id,mcp_connection_ids,session_reference)
                VALUES($1,$2,'active',now()+interval '5 minutes','openrouter',TRUE,$3,$4::jsonb,$5)
                ON CONFLICT DO NOTHING RETURNING expires_at""",owner,payload.session_id,payload.conversation_id,json.dumps(payload.mcp_connection_ids),ref)
            if expiry is None:raise HTTPException(409,"Voice session identity already used")
    return JSONResponse({"session_id":str(payload.session_id),"transport":"openrouter","expires_at":expiry.isoformat(),"duration_seconds":300},headers={"cache-control":"no-store"})

@router.post("/v2/personal/voice/openrouter/{session_id}/turn")
async def turn(session_id:UUID,payload:Utterance,request:Request):
    owner=await _owner(request,changing=True)
    try:raw=decode_wav(payload.audio)
    except ValueError:raise HTTPException(422,"Invalid audio") from None
    rid=uuid5(session_id,str(payload.event_id))
    digest=hashlib.sha256(raw).hexdigest()
    async with _conversation_db() as db:
        key="dz-openrouter-voice:"+owner+":"+str(session_id)
        if not await db.fetchval("SELECT pg_try_advisory_lock(hashtextextended($1,0))",key):
            raise HTTPException(409,"Voice turn already processing")
        try:
            row=await authority(owner,session_id)
            prior=await db.fetchrow("""SELECT audio_sha256 FROM dz_openrouter_voice_turns
                WHERE owner_id=$1 AND session_id=$2 AND event_id=$3""",owner,session_id,payload.event_id)
            if prior is not None:
                if prior["audio_sha256"]!=digest:raise HTTPException(409,"Voice event identity conflict")
                saved=await db.fetchrow("""SELECT response FROM dz_first_party_chat_requests
                    WHERE owner_id=$1 AND request_id=$2 AND status='completed'""",owner,rid)
                if saved is None:raise HTTPException(409,"Voice turn already attempted; outcome unconfirmed")
                result=saved["response"]
                if isinstance(result,str):result=json.loads(result)
                # Duplicate response is recoverable, never repeat paid STT or chat.
                await db.execute("""UPDATE dz_native_voice_sessions SET conversation_id=$3
                    WHERE owner_id=$1 AND session_id=$2 AND state='active'""",owner,session_id,UUID(result["conversation_id"]))
                return {**result,"event_id":str(payload.event_id),"speech_segments":len(segments(result["message"]))}
            count=await db.fetchval("SELECT count(*) FROM dz_openrouter_voice_turns WHERE owner_id=$1 AND session_id=$2",owner,session_id)
            if count>=MAX_TURNS:raise HTTPException(429,"Voice turn allowance reached")
            await db.execute("""INSERT INTO dz_openrouter_voice_turns(owner_id,session_id,event_id,request_id,audio_sha256)
                VALUES($1,$2,$3,$4,$5)""",owner,session_id,payload.event_id,rid,digest)
            await authority(owner,session_id)
            response=await gateway(request,"/audio/transcriptions",{"model":STT,"input_audio":{"data":payload.audio,"format":"wav"}})
            try:transcript=json.loads(response.body)["text"].strip()
            except (ValueError,KeyError,TypeError,AttributeError):raise HTTPException(502,"Invalid transcription") from None
            if not transcript:return {"event_id":str(payload.event_id),"transcript":"","speech_segments":0,"status":"no_speech"}
            if len(transcript)>12000:raise HTTPException(422,"Transcript exceeds bound")
            row=await authority(owner,session_id)
            choices=row["mcp_connection_ids"]
            if isinstance(choices,str):choices=json.loads(choices)
            async def reauthorize():await authority(owner,session_id)
            result=await _chat_owned(ChatInput(message=transcript,request_id=rid,conversation_id=row["conversation_id"],
                mcp_connection_ids=choices),request,owner,authority=reauthorize)
            await db.execute("""UPDATE dz_native_voice_sessions SET conversation_id=$3
                WHERE owner_id=$1 AND session_id=$2 AND state='active'""",owner,session_id,UUID(result["conversation_id"]))
            return {**result,"transcript":transcript,"event_id":str(payload.event_id),"speech_segments":len(segments(result["message"]))}
        finally:await db.execute("SELECT pg_advisory_unlock(hashtextextended($1,0))",key)

@router.post("/v2/personal/voice/openrouter/{session_id}/speech/{event_id}/{index}")
async def speech(session_id:UUID,event_id:UUID,index:int,request:Request):
    owner=await _owner(request,changing=True)
    await authority(owner,session_id)
    if not 0<=index<MAX_SEGMENTS:raise HTTPException(404,"Speech segment unavailable")
    async with _conversation_db() as db:
        row=await db.fetchrow("""SELECT c.response FROM dz_openrouter_voice_turns v
            JOIN dz_first_party_chat_requests c ON c.owner_id=v.owner_id AND c.request_id=v.request_id
            WHERE v.owner_id=$1 AND v.session_id=$2 AND v.event_id=$3 AND c.status='completed'""",owner,session_id,event_id)
        if row is None:raise HTTPException(404,"Completed voice answer unavailable")
        result=row["response"]
        if isinstance(result,str):result=json.loads(result)
        parts=segments(result["message"])
        if index>=len(parts):raise HTTPException(404,"Speech segment unavailable")
        inserted=await db.fetchval("""INSERT INTO dz_openrouter_voice_speech(owner_id,session_id,event_id,segment)
            VALUES($1,$2,$3,$4) ON CONFLICT DO NOTHING RETURNING segment""",owner,session_id,event_id,index)
        if inserted is None:raise HTTPException(409,"Speech segment already attempted")
    await authority(owner,session_id)
    response=await gateway(request,"/audio/speech",{"model":TTS,"input":parts[index],"voice":VOICE,"response_format":"mp3"})
    if not response.headers.get("content-type","").startswith("audio/") or not 16<=len(response.body)<=5*1024*1024:
        raise HTTPException(502,"Invalid speech output")
    await authority(owner,session_id)
    return response

@router.post("/v2/personal/voice/openrouter/{session_id}/end")
async def end(session_id:UUID,request:Request):
    owner=await _owner(request,changing=True)
    async with _conversation_db() as db:
        row=await db.fetchval("""UPDATE dz_native_voice_sessions SET state='closed',updated_at=now()
            WHERE owner_id=$1 AND session_id=$2 AND transport='openrouter' RETURNING session_id""",owner,session_id)
    if row is None:raise HTTPException(404,"Voice session not found")
    return {"session_id":str(session_id),"state":"closed"}
