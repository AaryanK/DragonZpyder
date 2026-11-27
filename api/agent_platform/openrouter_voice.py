"""Transport-independent utterance voice. OpenRouter is the speech provider.

No LiveKit or Deepgram service is required. The provider gateway retains the
existing production inference key, shared admission quota and audit. Staging
retains its independently capped test key. Audio is not stored; only
canonical chat transcripts, request receipts and irreversible attempt fences.
"""
from __future__ import annotations
import asyncio
import base64
import hmac
import secrets
from typing import Literal
import hashlib
import io
import json
import logging
import os
import re
import struct
import wave
from uuid import UUID,uuid5
from pathlib import Path

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

log=logging.getLogger(__name__)
_schema_ready=False

def production_voice():
    return os.getenv("RAILWAY_ENVIRONMENT_NAME")=="production"

def provider_key():
    """Use the existing inference credential in production, never duplicate it."""
    return os.getenv("OPENROUTER_API_KEY" if production_voice() else
                     "DRAGONZPYDER_AGENT_MEDIA_OPENROUTER_API_KEY","")

def _base_enabled():
    return all(os.getenv(key)=="1" for key in (
        "DRAGONZPYDER_FIRST_PARTY_CHAT_ENABLED","DRAGONZPYDER_FIRST_PARTY_REQUEST_LEDGER_ENABLED",
        "DRAGONZPYDER_AGENTS_ENABLED","DRAGONZPYDER_IDENTITY_HTTP_ENABLED"))

def enabled():
    if not _base_enabled() or len(provider_key())<20:
        return False
    if production_voice():
        from usage_ledger import ledger
        # Existing explicit opt-out remains a rollback control, not a required flag.
        return os.getenv("DRAGONZPYDER_OPENROUTER_VOICE_ENABLED")!="0" and _schema_ready and ledger.available
    return os.getenv("DRAGONZPYDER_OPENROUTER_VOICE_ENABLED")=="1"

async def prepare_production_schema():
    """Apply the four reviewed additive migrations atomically to the existing
    agent database. No role/grant changes; insufficient privileges or absent
    storage leave voice unavailable without disrupting existing text chat.
    """
    global _schema_ready
    _schema_ready=False
    if not production_voice() or not _base_enabled() or len(provider_key())<20 or os.getenv("DRAGONZPYDER_OPENROUTER_VOICE_ENABLED")=="0":
        return
    from usage_ledger import ledger
    if not ledger.available:
        log.warning("Production voice readiness: usage ledger unavailable")
        return
    migrations=Path(__file__).resolve().parent/"migrations"
    try:
        async with asyncio.timeout(20):
            async with _conversation_db() as db:
                async with db.transaction():
                    await db.execute("SET LOCAL lock_timeout = '3s'")
                    await db.execute("SET LOCAL statement_timeout = '8s'")
                    await db.execute("SELECT pg_advisory_xact_lock(hashtextextended($1,0))","dz-production-voice-schema-v1")
                    for name in ("20261125_first_party_request_ledger.sql","20261125_native_voice.sql",
                                 "20261126_modular_voice.sql","20261126_openrouter_voice.sql"):
                        await db.execute((migrations/name).read_text(encoding="utf-8"))
                    # Readiness must include the actual canonical conversation storage.
                    await db.execute("SELECT id,owner_id FROM dz_first_party_conversations LIMIT 0")
                    await db.execute("SELECT request_id,cancel_requested FROM dz_first_party_chat_requests LIMIT 0")
                    await db.execute("SELECT session_id,transport,source_channel,bridge_token_sha256 FROM dz_native_voice_sessions LIMIT 0")
                    await db.execute("SELECT event_id,request_id FROM dz_openrouter_voice_turns LIMIT 0")
                    await db.execute("SELECT event_id,segment FROM dz_openrouter_voice_speech LIMIT 0")
        _schema_ready=True
        log.info("Production voice readiness: schema ready")
    except Exception:
        # Do not log DSNs, SQL error data, or credentials.
        log.warning("Production voice readiness: schema unavailable; voice remains disabled")

async def speech_budget_ready(http):
    """Production uses the existing shared account and persistent quota; staging
    continues to require a provider-enforced non-resetting $0.50 test cap."""
    from usage_ledger import ledger
    if not ledger.available or len(provider_key())<20:
        return False
    if production_voice():
        return enabled()
    from .key_budget import verify_key_budget
    return (await verify_key_budget(http,provider_key())).get("approved") is True

async def admit_production_speech():
    """Atomic shared hourly count admission, not a hard USD spending ceiling."""
    if not production_voice():
        return True
    from usage_ledger import ledger
    try:
        limit=max(1,min(1000,int(os.getenv("DRAGONZPYDER_RUNTIME_CALLS_PER_HOUR","120"))))
        return bool(await ledger.charge_agent_hour(limit))
    except Exception:
        return False


class SessionOffer(Offer):
    source:Literal["browser","android","ios","discord","telephony","external"]="browser"
    delegate:bool=Field(default=False,strict=True)

class Utterance(BaseModel):
    model_config=ConfigDict(extra="forbid")
    event_id:UUID
    audio:str=Field(min_length=60,max_length=7680060)
    format:Literal["wav","pcm_s16le","mulaw","alaw"]="wav"
    sample_rate:Literal[8000,16000,24000,48000]|None=None
    channels:Literal[1,2]|None=None

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

def _g711(value,kind):
    if kind=="mulaw":
        u=(~value)&255
        magnitude=(((u&15)<<3)+132)<<((u>>4)&7)
        return 132-magnitude if u&128 else magnitude-132
    a=value^85
    t=(a&15)<<4
    segment=(a&112)>>4
    t+=8 if segment==0 else 264
    if segment>1:t<<=segment-1
    return t if a&128 else -t

def normalize_audio(payload):
    """Normalize bounded PCM and G.711 audio; packet demux remains in adapters."""
    if payload.format=="wav":
        if payload.sample_rate not in (None,16000) or payload.channels not in (None,1):
            raise ValueError("WAV metadata mismatch")
        return decode_wav(payload.audio)
    rate,channels=payload.sample_rate,payload.channels
    if rate is None or channels is None or (payload.format!="pcm_s16le" and (rate!=8000 or channels!=1)):
        raise ValueError("Explicit supported source audio metadata required")
    width=2 if payload.format=="pcm_s16le" else 1
    max_bytes=rate*channels*width*30
    if len(payload.audio)>4*((max_bytes+2)//3):
        raise ValueError("Audio exceeds duration bound")
    raw=base64.b64decode(payload.audio,validate=True)
    if len(raw)%(width*channels):
        raise ValueError("Incomplete audio frame")
    count=len(raw)//(width*channels)
    if not rate*0.15<=count<=rate*30:
        raise ValueError("Invalid audio duration")
    if width==2:
        from array import array
        import sys
        values=array("h")
        values.frombytes(raw)
        if sys.byteorder!="little":values.byteswap()
        samples=[(values[i]+values[i+1])//2 for i in range(0,len(values),2)] if channels==2 else values
    else:samples=[_g711(x,payload.format) for x in raw]
    output=bytearray()
    for i in range(count*16000//rate):
        start=i*rate;end=(i+1)*rate
        if rate>=16000:
            first=start//16000;last=(end+15999)//16000
            value=sum(samples[j]*(min(end,(j+1)*16000)-max(start,j*16000))
                      for j in range(first,min(last,count)))//rate
        else:
            j,rem=divmod(start,16000)
            value=(samples[j]*(16000-rem)+samples[min(j+1,count-1)]*rem)//16000
        output.extend(struct.pack("<h",max(-32768,min(32767,value))))
    buf=io.BytesIO()
    with wave.open(buf,"wb") as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(16000);wav.writeframes(output)
    return decode_wav(base64.b64encode(buf.getvalue()).decode("ascii"))

def bridge_digest(value):
    return hashlib.sha256(("dz-voice-bridge:"+value).encode("ascii")).hexdigest()

async def voice_owner(request,session_id):
    """Cookie/CSRF for native clients; explicitly delegated session bearer for bridges."""
    header=request.headers.get("authorization","") if hasattr(request,"headers") else ""
    if not header:
        return await _owner(request,changing=True)
    if not enabled() or not re.fullmatch(r"Bearer dzv_[A-Za-z0-9_-]{43}",header):
        raise HTTPException(401,"Voice session grant required")
    digest=bridge_digest(header[7:])
    async with _conversation_db() as db:
        row=await db.fetchrow("""SELECT owner_id,bridge_token_sha256 FROM dz_native_voice_sessions
            WHERE session_id=$1 AND transport='openrouter' AND state='active'
            AND expires_at>now() AND bridge_token_sha256=$2""",session_id,digest)
    if row is None or not hmac.compare_digest(row["bridge_token_sha256"],digest):
        raise HTTPException(403,"Voice session grant rejected")
    await authority(row["owner_id"],session_id)
    return row["owner_id"]

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
        raise HTTPException(503,"Speech provider or budget unavailable; do not replay")
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

@router.post("/v2/personal/voice/sessions")
@router.post("/v2/personal/voice/openrouter/start",include_in_schema=False)
async def start(payload:SessionOffer,request:Request):
    owner=await _owner(request,changing=True)
    if not enabled():raise HTTPException(503,"OpenRouter voice unavailable")
    if len(set(payload.mcp_connection_ids))!=len(payload.mcp_connection_ids) or any(not re.fullmatch(r"c[a-f0-9]{30}",x) for x in payload.mcp_connection_ids):
        raise HTTPException(422,"Invalid voice account selection")
    if not await speech_budget_ready(request.app.state.http):
        raise HTTPException(503,"OpenRouter speech admission or accounting unavailable")
    ref=session_reference(request)
    await verify_authority(owner,ref)
    if payload.delegate and payload.source not in ("discord","telephony","external"):
        raise HTTPException(422,"Bridge grant requires an explicit external source")
    bridge_token="dzv_"+secrets.token_urlsafe(32) if payload.delegate else None
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
                (owner_id,session_id,state,expires_at,transport,agent_mode,conversation_id,mcp_connection_ids,session_reference,source_channel,bridge_token_sha256)
                VALUES($1,$2,'active',now()+interval '5 minutes','openrouter',TRUE,$3,$4::jsonb,$5,$6,$7)
                ON CONFLICT DO NOTHING RETURNING expires_at""",owner,payload.session_id,payload.conversation_id,json.dumps(payload.mcp_connection_ids),ref,payload.source,bridge_digest(bridge_token) if bridge_token else None)
            if expiry is None:raise HTTPException(409,"Voice session identity already used")
    result={"session_id":str(payload.session_id),"transport":"openrouter","source":payload.source,"expires_at":expiry.isoformat(),"duration_seconds":300,"contract_version":1,"input_formats":["wav","pcm_s16le","mulaw","alaw"],"output_format":"mp3"}
    if bridge_token:result["bridge_token"]=bridge_token
    return JSONResponse(result,headers={"cache-control":"no-store","referrer-policy":"no-referrer"})

@router.post("/v2/personal/voice/sessions/{session_id}/turn")
@router.post("/v2/personal/voice/openrouter/{session_id}/turn",include_in_schema=False)
async def turn(session_id:UUID,payload:Utterance,request:Request):
    owner=await voice_owner(request,session_id)
    await authority(owner,session_id)
    try:raw=await asyncio.to_thread(normalize_audio,payload)
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
            response=await gateway(request,"/audio/transcriptions",{"model":STT,"input_audio":{"data":base64.b64encode(raw).decode("ascii"),"format":"wav"}})
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

@router.post("/v2/personal/voice/sessions/{session_id}/speech/{event_id}/{index}")
@router.post("/v2/personal/voice/openrouter/{session_id}/speech/{event_id}/{index}",include_in_schema=False)
async def speech(session_id:UUID,event_id:UUID,index:int,request:Request):
    owner=await voice_owner(request,session_id)
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

@router.post("/v2/personal/voice/sessions/{session_id}/end")
@router.post("/v2/personal/voice/openrouter/{session_id}/end",include_in_schema=False)
async def end(session_id:UUID,request:Request):
    owner=await voice_owner(request,session_id)
    async with _conversation_db() as db:
        row=await db.fetchval("""UPDATE dz_native_voice_sessions SET state='closed',bridge_token_sha256=NULL,updated_at=now()
            WHERE owner_id=$1 AND session_id=$2 AND transport='openrouter' RETURNING session_id""",owner,session_id)
    if row is None:raise HTTPException(404,"Voice session not found")
    return {"session_id":str(session_id),"state":"closed"}
