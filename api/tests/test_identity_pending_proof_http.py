"""HTTP contracts for separately gated proof collection; no real credentials."""
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from identity import pending_proof_http as mod
from identity.password_login import LoginDenied
from identity.provider_challenges import ProviderChallenge
from identity.providers import ProviderProof

ISSUER = "https://api.dragonzpyder.xyz"


@pytest.fixture
def client(monkeypatch):
    app = FastAPI()
    app.include_router(mod.router)
    monkeypatch.setenv("DRAGONZPYDER_IMPORT_PROOF_ENABLED","1")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME","test")
    monkeypatch.setattr(mod,"_issuer",lambda: ISSUER)
    @asynccontextmanager
    async def db():
        yield object()
    monkeypatch.setattr(mod,"_identity_db",db)
    return TestClient(app,base_url=ISSUER,headers={"origin":ISSUER})


def test_proof_disabled_and_production_gate(client,monkeypatch):
    monkeypatch.delenv("DRAGONZPYDER_IMPORT_PROOF_ENABLED",raising=False)
    assert client.post("/identity/v1/import-proof/password",json={}).status_code==404
    monkeypatch.setenv("DRAGONZPYDER_IMPORT_PROOF_ENABLED","1")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME","production")
    monkeypatch.delenv("DRAGONZPYDER_IMPORT_PROOF_ALLOW_PRODUCTION",raising=False)
    assert client.post("/identity/v1/import-proof/password",json={}).status_code==503


def test_password_no_session_no_secret_echo(client,monkeypatch):
    ref=uuid4()
    async def prove(conn,*,email,password):
        if password!="synthetic-good":
            raise LoginDenied("Invalid credentials")
        return ref
    monkeypatch.setattr(mod,"prove_pending_password",prove)
    path="/identity/v1/import-proof/password"
    bad=client.post(path,json={"email":"x@example.test","password":"synthetic-secret","subject":"untrusted"})
    assert bad.status_code==400 and "synthetic-secret" not in bad.text
    denied=client.post(path,json={"email":"x@example.test","password":"synthetic-secret"})
    assert denied.status_code==401 and "synthetic-secret" not in denied.text
    assert client.post(path,json={},headers={"origin":"https://wrong.example"}).status_code==403
    good=client.post(path,json={"email":"x@example.test","password":"synthetic-good"})
    assert good.status_code==202
    assert good.json()=={"proof_reference":str(ref),"status":"awaiting_review"}
    assert "set-cookie" not in good.headers
    assert good.headers["cache-control"]=="no-store"


def test_google_challenge_purpose_and_verified_subject(client,monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_GOOGLE_CLIENT_ID","test-client")
    ref=uuid4()
    state,binding,nonce="s"*54,"b"*54,"n"*43
    async def create(conn,*,provider,purpose):
        assert (provider,purpose)==("google","pending_import")
        return ProviderChallenge(provider,state,binding,nonce)
    async def consume(conn,**kwargs):
        assert kwargs=={"provider":"google","state":state,"binding":binding,"purpose":"pending_import"}
        return ProviderChallenge("google",state,binding,nonce)
    def verify(credential,*,expected_nonce):
        assert credential=="synthetic-token" and expected_nonce==nonce
        return ProviderProof("google","verified-subject","x@example.test")
    async def prove(conn,proof):
        assert proof.provider_subject=="verified-subject"
        return ref
    monkeypatch.setattr(mod,"create_provider_challenge",create)
    monkeypatch.setattr(mod,"consume_provider_challenge",consume)
    monkeypatch.setattr(mod,"verify_google_identity_token",verify)
    monkeypatch.setattr(mod,"prove_pending_google",prove)
    start=client.post("/identity/v1/import-proof/google/start")
    assert start.status_code==200
    assert "__Host-dz_import_proof" in start.headers["set-cookie"]
    finish=client.post("/identity/v1/import-proof/google/complete",json={"state":state,"credential":"synthetic-token"})
    assert finish.status_code==202
    assert finish.json()["proof_reference"]==str(ref)
    assert "__Host-dz_identity" not in finish.headers.get("set-cookie","")
