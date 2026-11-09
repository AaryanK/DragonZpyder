"""Contract tests for the service-only Operly -> DragonZpyder harness route.

These do not make provider calls or execute Operly capabilities.
"""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_platform.router import router


class DummyRuntime:
    def __init__(self):
        self.calls = []

    async def run_report(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "answer": "Read-only evidence found.",
            "status": "completed",
            "successful_tools": ["operly_discover_capabilities", "operly_read_capability"],
            "termination_reason": None,
        }


def _app():
    app = FastAPI()
    app.include_router(router)
    app.state.agent_runtime = DummyRuntime()
    return app


def _body(**changes):
    body = {
        "thread_id": "conversation-1", "prompt": "Read my test calendar.",
        "scope_kind": "personal", "user_id": "user-test",
        "workspace_id": None, "lease_token": "opaque-lease-for-test-only",
    }
    body.update(changes)
    return body


def _enable(monkeypatch):
    for key in (
        "DRAGONZPYDER_AGENTS_ENABLED",
        "DRAGONZPYDER_AGENT_OPERLY_READONLY_ENABLED",
        "DRAGONZPYDER_AGENT_USE_GATEWAY",
        "DRAGONZPYDER_AGENT_PRODUCTION_MODE",
        "DRAGONZPYDER_AGENT_HARNESS_V2",
    ):
        monkeypatch.setenv(key, "1")
    monkeypatch.setenv("DRAGONZPYDER_OPERLY_AGENT_TOKEN", "a" * 48)


def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv("DRAGONZPYDER_AGENT_OPERLY_READONLY_ENABLED", raising=False)
    with TestClient(_app()) as client:
        response = client.post("/internal/agents/operly/run", json=_body())
    assert response.status_code == 503


def test_dedicated_service_auth_required(monkeypatch):
    _enable(monkeypatch)
    with TestClient(_app()) as client:
        response = client.post("/internal/agents/operly/run", json=_body())
    assert response.status_code == 401


def test_rejects_personal_workspace_mix(monkeypatch):
    _enable(monkeypatch)
    with TestClient(_app()) as client:
        response = client.post(
            "/internal/agents/operly/run", json=_body(workspace_id="not-allowed"),
            headers={"Authorization": "Bearer " + "a" * 48},
        )
    assert response.status_code == 400


def test_uses_dragonzpyder_langgraph_and_never_claims_verified_goal(monkeypatch):
    _enable(monkeypatch)
    monkeypatch.setattr(
        "agent_platform.operly_broker.readonly_tools",
        lambda lease: ["fake-readonly-tool"],
    )
    app = _app()
    with TestClient(app) as client:
        response = client.post(
            "/internal/agents/operly/run", json=_body(),
            headers={"Authorization": "Bearer " + "a" * 48},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Read-only evidence found."
    assert body["status"] == "completed"
    assert body["objective_verified"] is False
    assert app.state.agent_runtime.calls[0]["external_tools"] == ["fake-readonly-tool"]
    assert app.state.agent_runtime.calls[0]["service_id"].startswith("operly-")
