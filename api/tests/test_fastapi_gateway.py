"""Contract checks for the migrated DragonZpyder internal API."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from main import app, runtime

TOKEN = "t" * 40
HEADERS = {"Authorization": "Bearer " + TOKEN}
BODY = {"model": "openai/gpt-oss-120b", "messages": [{"role": "user", "content": "hi"}]}


def test_health_and_auth(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_RUNTIME_TOKEN", TOKEN)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    with TestClient(app) as client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/v1/models").status_code == 401
        assert client.get("/v1/models", headers=HEADERS).json()["data"][0]["id"] == BODY["model"]
        assert client.get("/internal/v1/models", headers=HEADERS).status_code == 200
        assert client.get("/not-found").status_code == 404


def test_reject_unsafe_payloads(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_RUNTIME_TOKEN", TOKEN)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    with TestClient(app) as client:
        h = {**HEADERS, "Content-Type": "application/json"}
        assert client.post("/internal/v1/chat/completions", json={**BODY, "tools": [{"type": "function"}]}, headers=h).status_code == 400
        assert client.post("/v1/chat/completions", json={**BODY, "model": "unknown"}, headers=h).status_code == 403
        assert client.post("/v1/chat/completions", content=b"no", headers=h).status_code == 400
        assert client.post("/v1/chat/completions", json={**BODY, "messages": [{"role": "tool", "content": "x"}]}, headers=h).status_code == 400


def test_no_browser_credentials_and_route_aliases(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_RUNTIME_TOKEN", TOKEN)
    with TestClient(app) as client:
        assert client.get("/v1/models", headers={"Cookie": "session=fake"}).status_code == 401
        assert client.get("/v1/models", headers=HEADERS).headers["access-control-allow-origin"] == "null"
        assert client.get("/internal/v1/health", headers=HEADERS).status_code == 200
        assert client.post("/v1/chat/completions", headers=HEADERS).status_code == 415



def test_parallel_inference_parent_is_reserved_and_settled_at_real_gateway_route(monkeypatch):
    """No paid provider; exercise authenticated FastAPI request to reservation."""
    import json
    from uuid import uuid4
    import main

    token="p"*44
    monkeypatch.setenv("DRAGONZPYDER_APP_KEYS_JSON",json.dumps({"agent-runtime":token}))
    monkeypatch.setenv("DRAGONZPYDER_AGENT_TOOL_CALLS_ENABLED","1")
    monkeypatch.setenv("OPENROUTER_API_KEY","not-real")
    monkeypatch.setenv("DRAGONZPYDER_RUNTIME_ALLOWED_MODELS","openai/gpt-oss-120b")
    monkeypatch.delenv("DRAGONZPYDER_AGENT_PAID_TEST_MAX_KEY_LIMIT_USD",raising=False)
    monkeypatch.delenv("DRAGONZPYDER_STAGING_PAID_TEST_CAP_USD",raising=False)
    monkeypatch.delenv("RAILWAY_ENVIRONMENT_NAME",raising=False)

    class Ledger:
        available=True
        required=True
        async def open(self): pass
        async def close(self): pass
        async def record(self,**kwargs): return True
    monkeypatch.setattr(main,"ledger",Ledger())

    calls=[]
    class Store:
        async def reserve(self,**kwargs):
            calls.append(("reserve",kwargs))
            return True
        async def settle(self,**kwargs):
            calls.append(("settle",kwargs))
            return True
    monkeypatch.setattr(main.parent_budget,"store",Store())
    class Upstream:
        status_code=200
        headers={}
        def json(self):
            return {"model":"openai/gpt-oss-120b","id":"fake-generation",
                "choices":[{"index":0,"message":{"role":"assistant",
                             "content":"offline test result"},"finish_reason":"stop"}],
                "usage":{"prompt_tokens":5,"completion_tokens":4,"cost":0.000003}}
    async def fake_post(*args,**kwargs):
        assert kwargs["json"]["provider"]["max_price"]=={
            "prompt":1.0,"completion":4.0}
        assert kwargs["json"]["usage"]=={"include":True}
        assert calls and calls[0][0]=="reserve"
        return Upstream()

    with TestClient(main.app) as client:
        monkeypatch.setattr(main.app.state.http,"post",fake_post)
        job=str(uuid4())
        headers={"Authorization":"Bearer "+token,
                 "Content-Type":"application/json",
                 "X-DragonZpyder-Parent-Job-Id":job}
        body={"model":"openai/gpt-oss-120b",
              "messages":[{"role":"user","content":"Offline reservation test"}],
              "max_tokens":100, "stream":False}
        resp=client.post("/internal/agent/v1/chat/completions",
                         json=body,headers=headers)
    assert resp.status_code==200,resp.text
    assert [x[0] for x in calls]==["reserve","settle"]
    assert calls[0][1]["job_id"]==job
    assert calls[1][1]["actual_usd"]=="0.0000030000"
