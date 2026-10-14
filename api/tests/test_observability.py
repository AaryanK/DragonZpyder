"""Gateway usage accounting, auth separation, and observability contract."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from fastapi.testclient import TestClient

from main import app
from telemetry import client_identity, ledger, content_cipher

TOKEN = "t" * 40
ADMIN = "a" * 40
CLIENT = "q" * 40
BODY = {"model": "openai/gpt-oss-120b", "messages": [{"role": "user", "content": "Hello"}]}


def upstream(request: httpx.Request):
    assert request.url.path == "/api/v1/chat/completions"
    assert request.headers["authorization"] == "Bearer test"
    return httpx.Response(200, json={
        "id": "gen-1", "model": BODY["model"],
        "choices": [{"message": {"content": "Hello!"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10,
                  "prompt_tokens_details": {"cached_tokens": 2}, "cost": 0.0003},
    })


def test_traced_completion_returns_verified_provider_usage(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_RUNTIME_TOKEN", TOKEN)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    monkeypatch.delenv("DRAGONZPYDER_REQUIRE_LEDGER", raising=False)
    with TestClient(app) as client:
        old = client.app.state.http
        client.app.state.http = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
        try:
            r = client.post("/v1/chat/completions", json=BODY,
                            headers={"authorization": "Bearer " + TOKEN,
                                     "traceparent": "00-11223344556677889900aabbccddeeff-1111111111111111-01"})
            assert r.status_code == 200, r.text
            assert len(r.headers["x-trace-id"]) == 32
            assert len(r.headers["x-dragonzpyder-request-id"]) == 32
            assert r.json()["usage"]["total_tokens"] == 10
            assert r.json()["usage"]["cost"] == 0.0003
        finally:
            client.app.state.http = old


def test_admin_only_separate_token_and_not_browser_session(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_RUNTIME_TOKEN", TOKEN)
    monkeypatch.setenv("DRAGONZPYDER_ADMIN_TOKEN", ADMIN)
    with TestClient(app) as client:
        assert client.get("/internal/admin/v1/summary",
                          headers={"authorization": "Bearer " + TOKEN}).status_code == 401
        assert client.get("/internal/admin/v1/summary", headers={"cookie": "is_admin=1"}).status_code == 401
        good = {"authorization": "Bearer " + ADMIN}
        assert client.get("/internal/admin/v1/summary", headers=good).status_code == 200
        assert client.get("/internal/admin/v1/events", headers=good).status_code == 200
        assert client.get("/internal/admin/v1/events/notfound", headers=good).status_code == 404


def test_client_tokens_are_attributed_server_side(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_CLIENT_TOKENS", '{"querypedia":"' + CLIENT + '"}')
    monkeypatch.setenv("DRAGONZPYDER_RUNTIME_TOKEN", TOKEN)
    class Fake:
        headers = {"authorization": "Bearer " + CLIENT, "x-dragonzpyder-app": "other"}
    assert client_identity(Fake()) == "querypedia"
    Fake.headers = {"authorization": "Bearer " + TOKEN, "x-dragonzpyder-app": "querypedia"}
    assert client_identity(Fake()) == "legacy-internal"


def test_full_payload_capture_requires_explicit_encryption(monkeypatch):
    monkeypatch.delenv("DRAGONZPYDER_CAPTURE_MODEL_PAYLOADS", raising=False)
    assert content_cipher() is None
    monkeypatch.setenv("DRAGONZPYDER_CAPTURE_MODEL_PAYLOADS", "true")
    monkeypatch.delenv("DRAGONZPYDER_AUDIT_ENCRYPTION_KEY", raising=False)
    import pytest
    with pytest.raises(ValueError, match="requires"):
        content_cipher()


def test_durable_storage_fail_closed_mode(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_RUNTIME_TOKEN", TOKEN)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    monkeypatch.setenv("DRAGONZPYDER_REQUIRE_LEDGER", "true")
    with TestClient(app) as client:
        if not ledger.configured:
            r = client.post("/v1/chat/completions", json=BODY,
                            headers={"authorization": "Bearer " + TOKEN})
            assert r.status_code == 503
            assert "Durable usage ledger" in r.text
