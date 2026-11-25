"""Read-only archive HTTP contracts with synthetic rows."""
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime,timezone
from uuid import uuid4
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agent_platform import personal_history_http as mod


@pytest.fixture
def client(monkeypatch):
    app=FastAPI()
    app.include_router(mod.router)
    monkeypatch.setenv("DRAGONZPYDER_PERSONAL_HISTORY_ARCHIVE_ENABLED","1")
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_HTTP_ENABLED","1")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME","test")
    async def owner(request,*,changing):
        assert not changing
        return "owner-a"
    monkeypatch.setattr(mod,"_owner",owner)
    return TestClient(app)


def test_archive_gate(client,monkeypatch):
    monkeypatch.delenv("DRAGONZPYDER_PERSONAL_HISTORY_ARCHIVE_ENABLED")
    assert client.get("/v2/personal/archive/conversations").status_code==404
    monkeypatch.setenv("DRAGONZPYDER_PERSONAL_HISTORY_ARCHIVE_ENABLED","1")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME","production")
    monkeypatch.delenv("DRAGONZPYDER_IDENTITY_ALLOW_PRODUCTION",raising=False)
    assert client.get("/v2/personal/archive/conversations").status_code==503


def test_archive_owner_filter_and_pagination(client,monkeypatch):
    cid,mid=uuid4(),uuid4()
    now=datetime.now(timezone.utc)
    class DB:
        async def fetchval(self,query,*args):
            assert "owner_id=$2" in query and args[1]=="owner-a"
            return args[0]==cid
        async def fetch(self,query,*args):
            if "FROM public.dz_imported_personal_messages" in query:
                assert "conversation_id=$1 AND owner_id=$2" in query
                assert args==(cid,"owner-a",0)
                return [{"id":mid,"role":"assistant","content":"Synthetic private transcript","created_at":now}]
            assert "WHERE owner_id=$1" in query
            assert args==("owner-a",0)
            return [{"id":cid,"title":"Archived","created_at":now,"updated_at":now,"channel":"web","surface":"personal"}]
    @asynccontextmanager
    async def db():
        yield DB()
    monkeypatch.setattr(mod,"_conversation_db",db)
    base="/v2/personal/archive/conversations"
    result=client.get(base+"?owner_id=owner-b")
    assert result.status_code==200 and result.json()["conversations"][0]["id"]==str(cid)
    assert result.headers["cache-control"]=="no-store"
    assert client.get(base+"/"+str(uuid4())+"/messages").status_code==404
    result=client.get(base+"/"+str(cid)+"/messages")
    assert result.status_code==200
    assert result.json()["messages"][0]["content"]=="Synthetic private transcript"
    assert result.headers["cache-control"]=="no-store"
    assert client.get(base+"?offset=-1").status_code==400
    assert client.post(base,json={}).status_code==405
