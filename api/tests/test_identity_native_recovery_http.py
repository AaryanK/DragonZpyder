"""Native pending recovery HTTP tests; fake transport, no real email."""
import sys
from pathlib import Path
from contextlib import asynccontextmanager
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from identity import native_recovery_http as mod
from identity import pending_proof_http as proof
from identity.passwords import verify_password

ISSUER="https://api.dragonzpyder.xyz"


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_IMPORT_PROOF_ENABLED","1")
    monkeypatch.setenv("DRAGONZPYDER_NATIVE_PENDING_RECOVERY_ENABLED","1")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME","test")
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_GRANT_HASH_KEY","synthetic-test-pepper-0123456789abcdef")
    monkeypatch.setattr(proof,"_issuer",lambda:ISSUER)
    monkeypatch.setattr(mod,"_smtp_settings",lambda:("smtp.example.test","sender@example.test","test","secret"))
    sent=[]; calls=[]
    class DB:
        async def fetchval(self,q,*args):
            calls.append((q,args))
            if "identity_login_rate_limits" in q: return 1
            if "issue_pending_recovery" in q:
                return args[0] if args[0]=="eligible@example.test" else None
            if "redeem_pending_recovery" in q:
                return args[0]=="eligible@example.test" and args[1]==mod._secret_digest("pending-recovery:"+sent[0][1]) and verify_password("Synthetic-strong-123!",args[2])
            raise AssertionError("Unexpected database query")
    @asynccontextmanager
    async def db(): yield DB()
    monkeypatch.setattr(mod,"_identity_db",db)
    monkeypatch.setattr(mod,"_deliver",lambda recipient,token:sent.append((recipient,token)))
    app=FastAPI(); app.include_router(mod.router)
    return TestClient(app,base_url=ISSUER,headers={"origin":ISSUER}),sent,calls


def test_recovery_issuance_and_completion(setup,monkeypatch):
    client,sent,calls=setup
    root="/identity/v1/import-proof/recovery"
    a=client.post(root+"/start",json={"email":"eligible@example.test"})
    b=client.post(root+"/start",json={"email":"unknown@example.test"})
    assert a.status_code==b.status_code==202 and a.json()==b.json()=={"status":"if_eligible_sent"}
    assert len(sent)==1 and len(sent[0][1])==43
    code=sent[0][1]
    assert code not in a.text
    bad=client.post(root+"/complete",json={"email":"other@example.test","code":code,"password":"Synthetic-strong-123!"})
    assert bad.status_code==401
    good=client.post(root+"/complete",json={"email":"eligible@example.test","code":code,"password":"Synthetic-strong-123!"})
    assert good.status_code==202 and good.json()["status"]=="awaiting_review"
    assert "set-cookie" not in good.headers and code not in good.text
    assert all(code not in str(args) and "Synthetic-strong-123!" not in str(args) for _,args in calls)
    assert client.post(root+"/start",headers={"origin":"https://evil.invalid"},json={}).status_code==403
    monkeypatch.delenv("DRAGONZPYDER_NATIVE_PENDING_RECOVERY_ENABLED")
    assert client.post(root+"/start",json={}).status_code==404


def test_delivery_failure_has_generic_response(setup,monkeypatch):
    client,sent,calls=setup
    def fail(*args): raise RuntimeError("sensitive upstream details")
    monkeypatch.setattr(mod,"_deliver",fail)
    result=client.post("/identity/v1/import-proof/recovery/start",json={"email":"eligible@example.test"})
    assert result.status_code==202 and "sensitive" not in result.text
