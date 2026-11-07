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
        css = client.get("/staging.css")
        assert css.status_code == 200
        assert css.headers["content-type"].startswith("text/css")
        html = client.get("/").text
        assert 'href="/staging.css"' in html
        assert "<style>" not in html
        assert "style-src 'self'" in client.get("/").headers["content-security-policy"]
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

def test_failure_details_do_not_leak_secrets():
    from staging_app import safe_failure, log_safe_failure
    from agent_platform.runtime import AgentPipelineError
    try:
        raise RuntimeError("PRIVATE_EXCEPTION_TEXT_NEVER_LOG")
    except RuntimeError as cause:
        try:
            raise AgentPipelineError("construction") from cause
        except AgentPipelineError as error:
            message, code = safe_failure(error)
            assert code == 502
            assert "PRIVATE_EXCEPTION_TEXT_NEVER_LOG" not in message
            log_safe_failure(error, "testref")


def test_synthetic_memory_requires_staging_auth_and_feature_flag(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_STAGING_PASSWORD", "r" * 40)
    monkeypatch.delenv("DRAGONZPYDER_MEMORY_TEST_ENABLED", raising=False)
    with TestClient(app) as client:
        assert client.post("/test-memory").status_code == 401
        r=client.post("/test-memory",headers={"x-staging-password":"r"*40})
        assert r.status_code == 503


def test_gateway_readiness_defaults_to_direct_dev(monkeypatch):
    import asyncio
    from agent_platform.staging_smokes import gateway_readiness
    monkeypatch.delenv("DRAGONZPYDER_AGENT_USE_GATEWAY", raising=False)
    assert asyncio.run(gateway_readiness()) == "direct_staging_only"


def test_memory_smoke_rejects_partial_success_without_paid_calls(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("DRAGONZPYDER_STAGING_PASSWORD", "r" * 40)
    monkeypatch.setenv("DRAGONZPYDER_MEMORY_TEST_ENABLED", "1")
    monkeypatch.setattr(
        "staging_app.synthetic_memory_smoke",
        lambda: {"memory_written": True, "memory_retrieved": False, "vector_records_deleted": True},
    )
    with TestClient(app) as client:
        response = client.post("/test-memory", headers={"x-staging-password": "r" * 40})
        assert response.status_code == 502
        assert "Synthetic memory smoke failed" in response.json()["detail"]



def test_hatchet_ping_requires_access_and_feature_flag(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_STAGING_PASSWORD", "r" * 40)
    monkeypatch.delenv("DRAGONZPYDER_HATCHET_TEST_ENABLED", raising=False)
    with TestClient(app) as client:
        assert client.post("/test-hatchet").status_code == 401
        result = client.post("/test-hatchet", headers={"x-staging-password":"r"*40})
        assert result.status_code == 503


def test_hatchet_ping_success_without_real_network(monkeypatch):
    import sys
    from types import SimpleNamespace
    monkeypatch.setenv("DRAGONZPYDER_STAGING_PASSWORD", "r" * 40)
    monkeypatch.setenv("DRAGONZPYDER_HATCHET_TEST_ENABLED", "1")
    monkeypatch.setenv("HATCHET_CLIENT_TOKEN", "test")
    from agent_platform.jobs import PingOutput
    class FakeTask:
        async def aio_run(self, value):
            assert value.message == "staging-healthcheck"
            return PingOutput(ok=True, message=value.message)
    monkeypatch.setattr("agent_platform.jobs.make_ping_task", lambda client: FakeTask())
    monkeypatch.setattr("hatchet_sdk.Hatchet", lambda: object())
    with TestClient(app) as client:
        result = client.post("/test-hatchet", headers={"x-staging-password":"r"*40})
        assert result.status_code == 200
        assert result.json()["worker_executed"] is True
