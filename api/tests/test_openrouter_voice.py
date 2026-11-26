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
