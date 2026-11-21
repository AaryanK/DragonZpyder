"""Usage attribution, tracing metadata and admin isolation tests."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from fastapi.testclient import TestClient

from main import app, caller_identity, ledger
from usage_ledger import UsageLedger, digest, token_usage

LEGACY = "L" * 48
APP_KEY = "Q" * 48
ADMIN = "A" * 48
BODY = {"model": "openai/gpt-oss-120b",
        "messages": [{"role": "user", "content": "What is the Moon?"}]}


def test_token_usage_never_assumes_missing_is_zero():
    assert token_usage({}) == {
        "input_tokens": None, "output_tokens": None, "total_tokens": None,
        "cache_read_tokens": None, "reasoning_tokens": None,
        "provider_cost_usd": None}
    result = token_usage({"usage": {"prompt_tokens": 124, "completion_tokens": 38,
                                   "total_tokens": 162, "cost": 0.00003412,
                                   "prompt_tokens_details": {"cached_tokens": 12},
                                   "completion_tokens_details": {"reasoning_tokens": 2}}})
    assert result["input_tokens"] == 124
    assert result["cache_read_tokens"] == 12
    assert result["reasoning_tokens"] == 2
    assert str(result["provider_cost_usd"]) == "0.0000341200"


def test_opt_in_payload_encryption_and_digest():
    import base64
    import os
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    db = UsageLedger()
    db.encryption_key = b"m" * 32
    payload = {"messages": [{"role": "user", "content": "Confidential"}]}
    request_id = "ab12"
    sealed = db.encrypt(payload, {"content": "Private result"}, request_id)
    assert sealed is not None
    assert b"Confidential" not in sealed
    decoded = json.loads(AESGCM(db.encryption_key).decrypt(
        sealed[:12], sealed[12:], request_id.encode()))
    assert decoded["request"] == payload
    assert digest(payload) != digest({"messages": []})


def test_app_key_isolation_and_model_trace(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_RUNTIME_TOKEN", LEGACY)
    monkeypatch.setenv("DRAGONZPYDER_APP_KEYS_JSON", json.dumps({"querypedia": APP_KEY}))
    monkeypatch.setenv("DRAGONZPYDER_ADMIN_TOKEN", ADMIN)
    monkeypatch.setenv("OPENROUTER_API_KEY", "mock-provider-key")
    events = []

    async def capture(**data):
        events.append(data)
        return True

    monkeypatch.setattr(ledger, "record", capture)

    def upstream(request):
        assert request.headers.get("authorization") == "Bearer mock-provider-key"
        assert request.headers.get("x-dragonzpyder-request-id")
        return httpx.Response(200, json={
            "id": "gen-moon", "model": "openai/gpt-oss-120b",
            "choices": [{"message": {"content": "The Moon is Earth's satellite."}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 22, "completion_tokens": 9, "total_tokens": 31,
                      "cost": 0.000009}}
        )

    with TestClient(app) as client:
        original = client.app.state.http
        client.app.state.http = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
        try:
            h = {"authorization": "Bearer " + APP_KEY}
            result = client.post("/internal/v1/chat/completions", json=BODY, headers=h)
            assert result.status_code == 200, result.text
            assert result.headers["x-dragonzpyder-audit"] == "persisted"
            assert len(result.headers["x-dragonzpyder-trace-id"]) == 32
            assert result.headers["x-dragonzpyder-request-id"] == events[0]["request_id"]
            assert events[0]["app_id"] == "querypedia"
            assert events[0]["generation_id"] == "gen-moon"
            assert events[0]["status"] == "ok"
            assert events[0]["response"]["usage"]["total_tokens"] == 31

            # A client-supplied app header cannot confer another application's identity.
            h2 = {"authorization": "Bearer " + LEGACY, "x-dragonzpyder-app": "querypedia"}
            result2 = client.post("/v1/chat/completions", json=BODY, headers=h2)
            assert result2.status_code == 200
            assert events[1]["app_id"] == "legacy"
            assert client.get("/internal/admin/usage",
                              headers={"authorization": "Bearer " + APP_KEY}).status_code == 401
        finally:
            client.app.state.http = original


def test_admin_scope_is_distinct(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_RUNTIME_TOKEN", LEGACY)
    monkeypatch.setenv("DRAGONZPYDER_ADMIN_TOKEN", ADMIN)

    async def stub_summary(**args):
        return {"totals": {"calls": 10, "provider_cost_usd": None},
                "groups": [], **args}

    monkeypatch.setattr(ledger, "summary", stub_summary)
    with TestClient(app) as client:
        h = {"authorization": "Bearer " + ADMIN}
        assert client.get("/internal/admin/usage", headers=h).json()["totals"]["calls"] == 10
        assert client.get("/internal/admin/usage?days=0", headers=h).status_code == 400
        assert client.get("/internal/admin/usage?days=7&app=querypedia", headers=h).json()["app_id"] == "querypedia"
        assert client.get("/internal/admin/usage",
                          headers={"authorization": "Bearer " + LEGACY}).status_code == 401
        assert client.get("/v1/models", headers=h).status_code == 401
        assert client.get("/internal/admin/usage").status_code == 401
