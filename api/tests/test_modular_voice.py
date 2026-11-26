import asyncio
import base64
import json
from types import SimpleNamespace
from uuid import uuid4
from pathlib import Path
import sys

import pytest
from fastapi import HTTPException
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_platform import modular_voice as voice

def configured(monkeypatch):
    for key in ("DRAGONZPYDER_MODULAR_VOICE_ENABLED", "DRAGONZPYDER_FIRST_PARTY_CHAT_ENABLED",
                "DRAGONZPYDER_FIRST_PARTY_REQUEST_LEDGER_ENABLED", "DRAGONZPYDER_AGENTS_ENABLED",
                "DRAGONZPYDER_IDENTITY_HTTP_ENABLED"):
        monkeypatch.setenv(key,"1")
    for key,value in {"LIVEKIT_URL":"wss://voice.example.org","LIVEKIT_API_KEY":"test",
                      "LIVEKIT_API_SECRET":"s"*32,"DRAGONZPYDER_VOICE_WORKER_TOKEN":"t"*40}.items():
        monkeypatch.setenv(key,value)

def test_disabled_and_bounded(monkeypatch):
    configured(monkeypatch)
    assert voice.enabled()
    monkeypatch.setenv("DRAGONZPYDER_MODULAR_VOICE_SECONDS","601")
    assert not voice.enabled()
    monkeypatch.setenv("DRAGONZPYDER_MODULAR_VOICE_SECONDS","300")
    monkeypatch.setenv("LIVEKIT_URL","http://voice.example.org")
    assert not voice.enabled()

def test_grant_only_microphone_in_exact_room(monkeypatch):
    configured(monkeypatch)
    sid = uuid4()
    token = voice.participant_token(sid)
    body=token.split(".")[1]
    claims=json.loads(base64.urlsafe_b64decode(body+"="*((-len(body))%4)))
    grant=claims["video"]
    assert claims["sub"]=="user-"+sid.hex
    assert grant["room"]==voice.room_name(sid)
    assert grant["roomJoin"] and grant["canPublishSources"]==["microphone"]
    assert not grant["canPublishData"]
    assert not grant.get("roomAdmin")
    assert claims["exp"]-claims["nbf"]<=90

def test_bad_worker_token_or_room_rejected_before_db(monkeypatch):
    configured(monkeypatch)
    sid=uuid4()
    scope=voice.WorkerScope(session_id=sid,room=voice.room_name(sid),nonce="n"*43)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(voice.worker_row(scope,SimpleNamespace(headers={})))
    assert exc.value.status_code==403
    bad=scope.model_copy(update={"room":voice.room_name(uuid4())})
    with pytest.raises(HTTPException) as exc:
        asyncio.run(voice.worker_row(bad,SimpleNamespace(headers={"authorization":"Bearer "+"t"*40})))
    assert exc.value.status_code==403
