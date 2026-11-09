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
