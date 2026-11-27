"""Offline contracts; no paid inference."""
import asyncio
import base64
import io
import json
import wave
from types import SimpleNamespace
from uuid import uuid4
from contextlib import asynccontextmanager
from pathlib import Path
import sys

import httpx
import pytest
from fastapi import HTTPException, Request
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agent_platform import openrouter_voice as voice
from provider_gateway import provider_request
from usage_ledger import ledger

def fixture_audio(frames=3200,channels=1,rate=16000):
    f=io.BytesIO()
    with wave.open(f,"wb") as w:
        w.setnchannels(channels);w.setsampwidth(2);w.setframerate(rate)
        w.writeframes(b"\0\0"*frames*channels)
    return base64.b64encode(f.getvalue()).decode()

def configured(monkeypatch):
    monkeypatch.delenv("RAILWAY_ENVIRONMENT_NAME",raising=False)
    for k in ("DRAGONZPYDER_OPENROUTER_VOICE_ENABLED","DRAGONZPYDER_FIRST_PARTY_CHAT_ENABLED",
              "DRAGONZPYDER_FIRST_PARTY_REQUEST_LEDGER_ENABLED","DRAGONZPYDER_AGENTS_ENABLED",
              "DRAGONZPYDER_IDENTITY_HTTP_ENABLED"):monkeypatch.setenv(k,"1")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_MEDIA_OPENROUTER_API_KEY","capped-"+"x"*32)
    for k in ("LIVEKIT_API_KEY","LIVEKIT_API_SECRET","DEEPGRAM_API_KEY"):monkeypatch.delenv(k,raising=False)

def test_enabled_without_extra_provider(monkeypatch):
    configured(monkeypatch)
    assert voice.enabled()
    monkeypatch.delenv("DRAGONZPYDER_AGENT_MEDIA_OPENROUTER_API_KEY")
    assert not voice.enabled()

def test_wav_and_speech_policy():
    raw=fixture_audio()
    assert len(voice.decode_wav(raw))==6444
    for invalid in (fixture_audio(rate=48000),fixture_audio(channels=2),fixture_audio(frames=100),
                    fixture_audio(frames=480001),raw[:-4],"not-base64"):
        with pytest.raises(ValueError):voice.decode_wav(invalid)
    voice.validate_voice_payload("/audio/transcriptions",{"model":voice.STT,"input_audio":{"data":raw,"format":"wav"}})
    voice.validate_voice_payload("/audio/speech",{"model":voice.TTS,"input":"Hello","voice":voice.VOICE,"response_format":"mp3"})
    with pytest.raises(ValueError):voice.validate_voice_payload("/audio/speech",{"model":"other/model","input":"Hello","voice":voice.VOICE,"response_format":"mp3"})
    chunks=voice.segments("This is a sentence. "*500)
    assert len(chunks)==4 and len(chunks[0])<=300 and all(len(x)<=900 for x in chunks)
    assert chunks[-1].endswith("The rest of the answer is in chat.")
    assert voice.segments("Short answer.")==["Short answer."]

def test_gateway_capped_key_no_extra_account_and_redacted_receipt(monkeypatch):
    configured(monkeypatch)
    monkeypatch.setenv("OPENROUTER_API_KEY","unrestricted-must-not-use")
    monkeypatch.setattr(ledger,"pool",object())
    events=[];calls=[]
    async def record(**kw):events.append(kw);return True
    monkeypatch.setattr(ledger,"record",record)
    class Runtime:
        async def enter(self):return True
        async def charge(self):return True
        async def leave(self):pass
    def handle(req):
        calls.append(req)
        assert req.headers["authorization"]=="Bearer capped-"+"x"*32
        if req.url.path.endswith("/key"):
            return httpx.Response(200,json={"data":{"limit":0.5,"limit_remaining":0.4,"limit_reset":None}})
        body=json.loads(req.content)
        if req.url.path.endswith("/transcriptions"):
            assert body["model"]==voice.STT
            return httpx.Response(200,json={"text":"private transcript","usage":{"cost":0.00001}},headers={"x-generation-id":"gen-stt"})
        assert body["model"]==voice.TTS and body["voice"]==voice.VOICE
        return httpx.Response(200,content=b"ID3"+b"x"*30,headers={"content-type":"audio/mpeg","x-generation-id":"gen-tts"})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
            app=SimpleNamespace(state=SimpleNamespace(http=http,provider_runtime=Runtime()))
            req=Request({"type":"http","method":"POST","path":"/test","headers":[(b"content-type",b"application/json")],"app":app})
            a=await voice.gateway(req,"/audio/transcriptions",{"model":voice.STT,"input_audio":{"data":fixture_audio(),"format":"wav"}})
            b=await voice.gateway(req,"/audio/speech",{"model":voice.TTS,"input":"private text","voice":voice.VOICE,"response_format":"mp3"})
            assert json.loads(a.body)["text"]=="private transcript" and b.body.startswith(b"ID3")
    asyncio.run(run())
    assert len(calls)==4 and len(events)==2
    assert all(e["app_id"]=="agent-voice" and set(e["request_payload"])=={"model","operation"} for e in events)
    assert events[0]["generation_id"]=="gen-stt" and events[1]["generation_id"]=="gen-tts"
    assert "private transcript" not in str(events) and "private text" not in str(events)

def test_authority_denied_without_matching_session(monkeypatch):
    configured(monkeypatch)
    class DB:
        async def fetchrow(self,sql,*args):
            assert "owner_id=$1" in sql and "transport='openrouter'" in sql
            return None
    @asynccontextmanager
    async def conn():yield DB()
    monkeypatch.setattr(voice,"_conversation_db",conn)
    with pytest.raises(HTTPException) as e:
        asyncio.run(voice.authority("wrong-owner",uuid4()))
    assert e.value.status_code==403


def test_postgres_voice_turn_and_speech_replay_fences(monkeypatch):
    """Actual transaction/advisory locks and constraints, mocked paid calls."""
    import os
    import asyncpg
    from fastapi.responses import JSONResponse,Response
    from uuid import UUID
    dsn=os.environ.get("DRAGONZPYDER_BUDGET_TEST_DSN")
    if not dsn:pytest.skip("Disposable PostgreSQL DSN required")
    configured(monkeypatch)
    owner="voice-test-"+uuid4().hex
    sid,cid,event=uuid4(),uuid4(),uuid4()
    current_owner=owner
    calls=[]
    @asynccontextmanager
    async def db_factory():
        db=await asyncpg.connect(dsn)
        try:yield db
        finally:await db.close()
    async def authenticated(request,changing):
        return current_owner
    async def verify(user,ref):
        assert user==owner and ref=="test-session-ref"
    async def gateway(request,path,payload):
        calls.append(path)
        if path.endswith("/transcriptions"):return JSONResponse({"text":"Hello agent"})
        return Response(b"ID3"+b"x"*30,media_type="audio/mpeg")
    async def chat(payload,request,user,authority):
        await authority()
        assert payload.message=="Hello agent" and user==owner
        calls.append("canonical_chat")
        result={"request_id":str(payload.request_id),"conversation_id":str(cid),"message":"Confirmed answer.","status":"completed"}
        async with db_factory() as db:
            await db.execute("""INSERT INTO dz_first_party_chat_requests
                (owner_id,request_id,fingerprint,conversation_id,status,response)
                VALUES($1,$2,$3,$4,'completed',$5::jsonb)""",
                owner,payload.request_id,"a"*64,cid,json.dumps(result))
        return result
    monkeypatch.setattr(voice,"_conversation_db",db_factory)
    monkeypatch.setattr(voice,"_owner",authenticated)
    monkeypatch.setattr(voice,"verify_authority",verify)
    monkeypatch.setattr(voice,"gateway",gateway)
    monkeypatch.setattr(voice,"_chat_owned",chat)
    async def run():
        nonlocal current_owner
        migrations=Path(__file__).resolve().parents[1]/"agent_platform/migrations"
        async with db_factory() as db:
            await db.execute((migrations/"20261122_first_party_chat.sql").read_text())
        # Exercise the real production bootstrap and a repeated startup against
        # the disposable PostgreSQL DB, without contacting a paid provider.
        with monkeypatch.context() as production:
            production.setenv("RAILWAY_ENVIRONMENT_NAME","production")
            production.setenv("OPENROUTER_API_KEY","existing-"+"x"*32)
            production.delenv("DRAGONZPYDER_OPENROUTER_VOICE_ENABLED")
            production.setattr(ledger,"pool",object())
            production.setattr(voice,"_schema_ready",False)
            await voice.prepare_production_schema()
            assert voice.enabled()
            await voice.prepare_production_schema()
            assert voice.enabled()
        async with db_factory() as db:
            await db.execute("""INSERT INTO dz_native_voice_sessions
                (owner_id,session_id,state,expires_at,transport,agent_mode,conversation_id,session_reference)
                VALUES($1,$2,'active',now()+interval '5 minutes','openrouter',TRUE,$3,'test-session-ref')""",owner,sid,cid)
        request=SimpleNamespace()
        payload=voice.Utterance(event_id=event,audio=fixture_audio())
        try:
            result=await voice.turn(sid,payload,request)
            assert result["message"]=="Confirmed answer." and result["speech_segments"]==1
            replay=await voice.turn(sid,payload,request)
            assert replay["request_id"]==result["request_id"]
            assert calls==["/audio/transcriptions","canonical_chat"]
            with pytest.raises(HTTPException) as conflict:
                await voice.turn(sid,voice.Utterance(event_id=event,audio=fixture_audio(3201)),request)
            assert conflict.value.status_code==409
            audio=await voice.speech(sid,event,0,request)
            assert audio.body.startswith(b"ID3")
            with pytest.raises(HTTPException) as duplicate:
                await voice.speech(sid,event,0,request)
            assert duplicate.value.status_code==409
            current_owner=owner+"-stranger"
            with pytest.raises(HTTPException) as denied:
                await voice.turn(sid,payload,request)
            assert denied.value.status_code==403
            current_owner=owner
            await voice.end(sid,request)
            with pytest.raises(HTTPException) as closed:
                await voice.speech(sid,event,0,request)
            assert closed.value.status_code==403
            assert calls==["/audio/transcriptions","canonical_chat","/audio/speech"]
        finally:
            async with db_factory() as db:
                for table in ("dz_openrouter_voice_speech","dz_openrouter_voice_turns","dz_native_voice_sessions","dz_first_party_chat_requests"):
                    await db.execute("DELETE FROM "+table+" WHERE owner_id=$1",owner)
    asyncio.run(run())


def test_transport_normalizes_native_and_phone_codecs():
    import struct
    for rate,channels in ((8000,1),(16000,1),(24000,2),(48000,2)):
        frame=struct.pack("<h",1200)*channels
        body=voice.Utterance(event_id=uuid4(),audio=base64.b64encode(frame*(rate//5)).decode(),
            format="pcm_s16le",sample_rate=rate,channels=channels)
        normalized=voice.normalize_audio(body)
        with wave.open(io.BytesIO(normalized),"rb") as wav:
            assert wav.getframerate()==16000 and wav.getnchannels()==1
            assert wav.getnframes()==3200
            assert wav.readframes(1)==struct.pack("<h",1200)
    for codec,octet,expected in (("mulaw",255,0),("mulaw",0,-32124),("alaw",213,8),("alaw",85,-8)):
        body=voice.Utterance(event_id=uuid4(),audio=base64.b64encode(bytes([octet])*1600).decode(),
            format=codec,sample_rate=8000,channels=1)
        with wave.open(io.BytesIO(voice.normalize_audio(body)),"rb") as wav:
            assert wav.getnframes()==3200
            assert wav.readframes(1)==struct.pack("<h",expected)
    bad=voice.Utterance(event_id=uuid4(),audio=base64.b64encode(b"x"*1600).decode(),
        format="mulaw",sample_rate=48000,channels=1)
    with pytest.raises(ValueError):voice.normalize_audio(bad)
    with pytest.raises(ValueError):voice.normalize_audio(bad.model_copy(update={"format":"pcm_s16le","sample_rate":16000,"channels":2,"audio":base64.b64encode(b"x"*1601).decode()}))

def test_bridge_token_bound_to_session_and_original_authority(monkeypatch):
    configured(monkeypatch)
    sid=uuid4()
    token="dzv_"+"x"*43
    digest=voice.bridge_digest(token)
    requests=[]
    class DB:
        async def fetchrow(self,sql,*args):
            assert "expires_at>now()" in sql and "state='active'" in sql
            return {"owner_id":"owner","bridge_token_sha256":digest} if args==(sid,digest) else None
    @asynccontextmanager
    async def db():yield DB()
    async def authority(owner,session):
        requests.append((owner,session))
        assert owner=="owner" and session==sid
    monkeypatch.setattr(voice,"_conversation_db",db)
    monkeypatch.setattr(voice,"authority",authority)
    async def run():
        request=SimpleNamespace(headers={"authorization":"Bearer "+token})
        assert await voice.voice_owner(request,sid)=="owner"
        with pytest.raises(HTTPException) as wrong:
            await voice.voice_owner(request,uuid4())
        assert wrong.value.status_code==403
        with pytest.raises(HTTPException) as invalid:
            await voice.voice_owner(SimpleNamespace(headers={"authorization":"Bearer invalid"}),sid)
        assert invalid.value.status_code==401
    asyncio.run(run())
    assert requests==[("owner",sid)]

def test_production_voice_uses_existing_key_without_new_flag(monkeypatch):
    configured(monkeypatch)
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME","production")
    monkeypatch.delenv("DRAGONZPYDER_OPENROUTER_VOICE_ENABLED")
    monkeypatch.delenv("DRAGONZPYDER_AGENT_MEDIA_OPENROUTER_API_KEY")
    monkeypatch.setenv("OPENROUTER_API_KEY","existing-"+ "x"*32)
    monkeypatch.setattr(ledger,"pool",object())
    monkeypatch.setattr(voice,"_schema_ready",False)
    assert not voice.enabled()
    monkeypatch.setattr(voice,"_schema_ready",True)
    assert voice.enabled()
    assert voice.provider_key()=="existing-"+"x"*32
    monkeypatch.setenv("DRAGONZPYDER_OPENROUTER_VOICE_ENABLED","0")
    assert not voice.enabled()
    monkeypatch.delenv("DRAGONZPYDER_OPENROUTER_VOICE_ENABLED")
    monkeypatch.setattr(ledger,"pool",None)
    assert not voice.enabled()

def test_production_voice_gateway_requires_atomic_quota(monkeypatch):
    configured(monkeypatch)
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME","production")
    monkeypatch.delenv("DRAGONZPYDER_OPENROUTER_VOICE_ENABLED")
    monkeypatch.delenv("DRAGONZPYDER_AGENT_MEDIA_OPENROUTER_API_KEY")
    monkeypatch.setenv("OPENROUTER_API_KEY","existing-"+"x"*32)
    monkeypatch.setattr(ledger,"pool",object())
    monkeypatch.setattr(voice,"_schema_ready",True)
    calls=[];charges=[]
    class Runtime:
        async def enter(self):return True
        async def charge(self):return True
        async def leave(self):pass
    async def record(**kw):return True
    monkeypatch.setattr(ledger,"record",record)
    async def quota(limit):
        charges.append(limit);return len(charges)==1
    monkeypatch.setattr(ledger,"charge_agent_hour",quota)
    def handle(req):
        calls.append(req)
        assert req.headers["authorization"]=="Bearer existing-"+"x"*32
        assert req.url.path.endswith("/audio/transcriptions")
        return httpx.Response(200,json={"text":"hello"})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
            app=SimpleNamespace(state=SimpleNamespace(http=http,provider_runtime=Runtime()))
            req=Request({"type":"http","method":"POST","path":"/test","headers":[(b"content-type",b"application/json")],"app":app})
            payload={"model":voice.STT,"input_audio":{"data":fixture_audio(),"format":"wav"}}
            assert (await voice.gateway(req,"/audio/transcriptions",payload)).status_code==200
            with pytest.raises(HTTPException) as denied:
                await voice.gateway(req,"/audio/transcriptions",payload)
            assert denied.value.status_code==429
            assert denied.value.detail=={"code":"voice_transcription_quota_or_rate_limit","outcome":"not_submitted"}
    asyncio.run(run())
    assert len(calls)==1 and len(charges)==2

def test_production_schema_failure_does_not_enable_voice(monkeypatch):
    configured(monkeypatch)
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME","production")
    monkeypatch.setenv("OPENROUTER_API_KEY","existing-"+"x"*32)
    monkeypatch.setattr(ledger,"pool",object())
    monkeypatch.setattr(voice,"_schema_ready",True)
    @asynccontextmanager
    async def unavailable():
        raise RuntimeError("migration role unavailable")
        yield
    monkeypatch.setattr(voice,"_conversation_db",unavailable)
    asyncio.run(voice.prepare_production_schema())
    assert not voice.enabled()

@pytest.mark.parametrize("path,status,outcome,code",[
    ("/audio/transcriptions",502,"not_submitted","voice_transcription_provider_unavailable"),
    ("/audio/speech",502,"committed","voice_speech_provider_unavailable"),
    ("/audio/transcriptions",503,"not_submitted","voice_transcription_service_or_accounting_unavailable"),
])
def test_gateway_reports_safe_voice_failure_phase(monkeypatch,path,status,outcome,code):
    import provider_gateway
    from fastapi.responses import JSONResponse
    async def reject(*args,**kwargs):
        return JSONResponse({"error":{"message":"private provider detail"}},status_code=status)
    monkeypatch.setattr(provider_gateway,"provider_request",reject)
    body=({"model":voice.STT,"input_audio":{"data":fixture_audio(),"format":"wav"}} if path.endswith("transcriptions")
          else {"model":voice.TTS,"input":"Hello","voice":voice.VOICE,"response_format":"mp3"})
    request=SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(provider_runtime=object())))
    with pytest.raises(HTTPException) as failure:
        asyncio.run(voice.gateway(request,path,body))
    assert failure.value.detail=={"code":code,"outcome":outcome}
