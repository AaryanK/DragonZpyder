import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from identity import mobile_provider as m

app=FastAPI()
app.include_router(m.router)

def test_mobile_gate_and_configuration(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_HTTP_ENABLED","1")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME","staging")
    monkeypatch.delenv("DRAGONZPYDER_IDENTITY_MOBILE_OAUTH_ENABLED",raising=False)
    with TestClient(app) as client:
        assert client.get("/identity/v1/mobile/capabilities").status_code==404
        monkeypatch.setenv("DRAGONZPYDER_IDENTITY_MOBILE_OAUTH_ENABLED","1")
        monkeypatch.setenv("DRAGONZPYDER_IDENTITY_DISCORD_CLIENT_ID","synthetic-id")
        monkeypatch.setenv("DRAGONZPYDER_IDENTITY_DISCORD_CLIENT_SECRET","synthetic-secret")
        monkeypatch.setenv("DRAGONZPYDER_IDENTITY_DISCORD_MOBILE_REDIRECT_URI","https://wrong.example")
        assert not client.get("/identity/v1/mobile/capabilities").json()["discord"]
        monkeypatch.setenv("DRAGONZPYDER_IDENTITY_DISCORD_MOBILE_REDIRECT_URI",m.PUBLIC+"/dz/identity/v1/mobile/discord/callback")
        assert client.get("/identity/v1/mobile/capabilities").json()["discord"]
        assert client.get("/identity/v1/mobile/discord/start?state=bad").status_code==400
        assert client.post("/identity/v1/mobile/discord/redeem",json={"ticket":"a"*43,"verifier":"b"*43},headers={"Origin":"https://evil.example"}).status_code in (403,503)

@pytest.mark.asyncio
async def test_mobile_claim_and_redemption_use_bound_atomic_queries(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_GRANT_HASH_KEY","synthetic-test-only-"+"x"*48)
    class DB:
        async def fetchrow(self,sql,*args):
            assert "callback_claimed_at IS NULL" in sql and "expires_at>now()" in sql
            assert args==(m.digest("state","s"*43),m.digest("browser","b"*43),"discord")
            return {"app_state":"a"*43}
        async def fetchval(self,sql,*args):
            assert "redeemed_at IS NULL" in sql and "expires_at>now()" in sql
            assert args==(m.digest("ticket","t"*43),m.pkce("v"*43),"discord")
            return "subject"
    db=DB()
    assert await m.claim_callback(db,"discord","s"*43,"bad") is None
    assert (await m.claim_callback(db,"discord","s"*43,"b"*43))["app_state"]=="a"*43
    assert await m.redeem_ticket(db,"discord","t"*43,"v"*43)=="subject"
