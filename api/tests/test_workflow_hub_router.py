"""Private workflow hub routing. No tool executions or hosted model calls."""
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_platform.workflows.router import router


def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_workflow_hub_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("DRAGONZPYDER_WORKFLOW_HUB_ENABLED", raising=False)
    with client() as http:
        response = http.post("/internal/workflows/preview", json={"schedule": None})
    assert response.status_code == 503


def test_workflow_hub_rejects_browser_without_operly_service_auth(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_WORKFLOW_HUB_ENABLED", "1")
    monkeypatch.setenv("DRAGONZPYDER_OPERLY_AGENT_TOKEN", "s" * 48)
    with client() as http:
        response = http.post("/internal/workflows/preview", json={"schedule": None})
        bad = http.post("/internal/workflows/preview",
                        headers={"Authorization": "Bearer " + "x" * 48},
                        json={"schedule": None})
    assert response.status_code == 401
    assert bad.status_code == 401


def test_validated_workflow_schedule_is_dragonzpyder_owned_and_does_not_execute(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_WORKFLOW_HUB_ENABLED", "1")
    monkeypatch.setenv("DRAGONZPYDER_OPERLY_AGENT_TOKEN", "s" * 48)
    headers = {"Authorization": "Bearer " + "s" * 48}
    payload = {
        "schedule": {"type":"cron","timezone":"UTC","expression":"0 9 * * 1"},
        "count": 2, "after":"2026-11-09T08:00:00+00:00",
        "spec": {"steps": [{"id":"read","capability_id":"workspace.summary.read","arguments":{}}]},
    }
    with client() as http:
        response = http.post("/internal/workflows/preview", headers=headers, json=payload)
    assert response.status_code == 200, response.text
    d = response.json()
    assert d["owner"] == "dragonzpyder"
    assert d["source"] == "langgraph-hatchet"
    assert d["occurrences"] == ["2026-11-09T09:00:00", "2026-11-16T09:00:00"]
    assert d["step_count"] == 1
    assert len(d["definition_sha256"]) == 64
    assert d["job_registered"] is False
    assert d["execution_started"] is False


def test_untrusted_invalid_dag_rejected_before_any_action(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_WORKFLOW_HUB_ENABLED", "1")
    monkeypatch.setenv("DRAGONZPYDER_OPERLY_AGENT_TOKEN", "s" * 48)
    with client() as http:
        response = http.post("/internal/workflows/preview",
            headers={"Authorization": "Bearer " + "s"*48},
            json={"spec": {"steps": [
                {"id": "x", "capability_id": "workflow.create"}
            ]}, "schedule": {"type": "cron", "expression":"* * *", "timezone":"UTC"}})
    assert response.status_code == 422
