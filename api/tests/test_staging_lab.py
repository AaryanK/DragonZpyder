"""Staging smoke UI contracts; never invokes a paid model."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from staging_app import app

def test_offline_lab_is_accessible_and_closed(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("DRAGONZPYDER_STAGING_PASSWORD", raising=False)
    with TestClient(app) as client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/").status_code == 200
        assert client.get("/staging.js").status_code == 200
        status = client.get("/status").json()
        assert status["prod_connected"] is False
        assert status["harness_ready"] is False
        assert client.post("/test", json={"thread_id":"t-1","prompt":"hello"}).status_code == 401

def test_test_password_is_not_sufficient_without_runtime(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("DRAGONZPYDER_STAGING_PASSWORD", "s" * 40)
    with TestClient(app) as client:
        response = client.post("/test", json={"thread_id":"t-1","prompt":"hello"},headers={"X-Staging-Password":"s"*40})
        assert response.status_code == 503
