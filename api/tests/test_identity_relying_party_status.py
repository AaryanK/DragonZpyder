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
        async def fetchrow(self,query,sid):
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
    assert client.post(path,json={"subject":"active-user"}).json()=={"active":True,"revoked_at":"2026-01-01T00:00:00+00:00"}
    for subject in ("disabled-user","absent-user"):
        assert client.post(path,json={"subject":subject}).json()=={"active":False,"revoked_at":None}
    assert client.post(path,json={"subject":"active-user"},headers={"authorization":"Bearer wrong"}).status_code==401
    assert client.post(path,json={"subject":"active-user","email":"not-accepted"}).status_code==400
    monkeypatch.delenv("DRAGONZPYDER_OPERLY_STATUS_ENABLED")
    assert client.post(path,json={"subject":"active-user"}).status_code==404
