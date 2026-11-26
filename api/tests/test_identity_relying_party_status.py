"""Synthetic relying-party status contract tests."""
import sys
from pathlib import Path
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from identity import relying_party_status as mod

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_HTTP_ENABLED","1")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME","test")
    monkeypatch.setenv("DRAGONZPYDER_OPERLY_STATUS_ENABLED","1")
    monkeypatch.setenv("DRAGONZPYDER_OPERLY_STATUS_SECRET","synthetic-test-only-"+"x"*43)
    class DB:
        async def fetchval(self,query,*args):
            if "to_regclass" in query: return True
            if args[0]=="active-user": return datetime(2026,1,2,tzinfo=timezone.utc)
            return None
        async def fetchrow(self,query,sid):
            if "identity_origin=\'native_google\'" in query:
                if sid=="00000000-0000-4000-8000-000000000001":
                    return {"subject":sid,"email":"synthetic@example.test","display_name":"Synthetic","email_verified_at":datetime(2026,1,1,tzinfo=timezone.utc)}
                return None
            if sid=="active-user":
                return {"active":True,"revoked_at":datetime(2026,1,1,tzinfo=timezone.utc)}
            if sid=="disabled-user":
                return {"active":False,"revoked_at":None}
            return None
    @asynccontextmanager
    async def db(): yield DB()
    monkeypatch.setattr(mod,"_identity_db",db)
    app=FastAPI();app.include_router(mod.router)
    return TestClient(app,headers={"authorization":"Bearer synthetic-test-only-"+"x"*43})

def test_status_contract(client,monkeypatch):
    path="/identity/v1/relying-party/status"
    assert client.post(path,json={"subject":"active-user"}).json()=={"active":True,"revoked_at":"2026-01-02T00:00:00+00:00"}
    for subject in ("disabled-user","absent-user"):
        assert client.post(path,json={"subject":subject}).json()=={"active":False,"revoked_at":None}
    assert client.post(path,json={"subject":"active-user"},headers={"authorization":"Bearer wrong"}).status_code==401
    assert client.post(path,json={"subject":"active-user","email":"not-accepted"}).status_code==400
    monkeypatch.delenv("DRAGONZPYDER_OPERLY_STATUS_ENABLED")
    assert client.post(path,json={"subject":"active-user"}).status_code==404


def test_native_projection_only_when_opted_in(client,monkeypatch):
    path="/identity/v1/relying-party/native-projection"
    sid="00000000-0000-4000-8000-000000000001"
    assert client.post(path,json={"subject":sid}).status_code==404
    monkeypatch.setenv("DRAGONZPYDER_OPERLY_NATIVE_PROJECTION_ENABLED","1")
    assert client.post(path,json={"subject":sid},headers={"authorization":"Bearer wrong"}).status_code==401
    result=client.post(path,json={"subject":sid})
    assert result.status_code==200 and result.json()["subject"]==sid
    assert set(result.json())=={"subject","email","display_name","email_verified_at"}
    assert client.post(path,json={"subject":"00000000-0000-4000-8000-000000000002"}).status_code==404
