"""No-paid-inference task route contracts: authentication, service scope, budget gates."""
import os
from uuid import uuid4
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_platform.web_tasks_router import router


class FakeActivityStore:
    def __init__(self):
        self.operations = []
    async def create(self, **kwargs):
        self.operations.append(("create", kwargs))
        return ({"task_id": str(uuid4()), "status": "queued",
                 "kind": kwargs["kind"], "attempts": 0}, True)
    async def list(self, **kwargs):
        self.operations.append(("list", kwargs))
        return []
    async def get(self, **kwargs):
        self.operations.append(("get", kwargs))
        if kwargs.get("admin"):
            return {"task_id": kwargs["task_id"], "status": "completed",
                    "events": [], "kind": "probe"}
        return {"task_id": kwargs["task_id"], "status": "queued", "events": []}
    async def cancel(self, **kwargs):
        self.operations.append(("cancel", kwargs))
        return {"task_id": kwargs["task_id"], "status": "cancelled"}
    async def append(self, *args, **kwargs):
        pass
    async def dispatch_failed(self, *args, **kwargs):
        pass


def api():
    application = FastAPI()
    application.include_router(router)
    application.state.activity_store = FakeActivityStore()
    return application


def test_browser_can_never_call_internal_harness_without_backend_secret(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_WEB_TASKS_ENABLED", "1")
    monkeypatch.setenv("DRAGONZPYDER_WEB_TASK_SERVICE_TOKEN", "s"*48)
    with TestClient(api()) as client:
        assert client.post("/internal/web-tasks/list", json={"owner": "person@example.test"}).status_code == 401
        assert client.post("/internal/web-tasks/admin/list", json={}).status_code == 401
        assert client.post("/internal/web-tasks/list",
            headers={"Authorization": "Bearer wrong"},
            json={"owner": "person@example.test"}).status_code == 401


def test_internal_admin_receives_only_operational_metadata(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_WEB_TASKS_ENABLED", "1")
    monkeypatch.setenv("DRAGONZPYDER_WEB_TASK_SERVICE_TOKEN", "s"*48)
    application = api()
    with TestClient(application) as client:
        token = {"Authorization": "Bearer " + "s"*48}
        assert client.post("/internal/web-tasks/list", headers=token,
            json={"owner": "person@example.test"}).json()["tasks"] == []
        x = client.post("/internal/web-tasks/admin/list", headers=token)
        assert x.status_code == 200 and x.json()["tasks"] == []
        assert application.state.activity_store.operations[-1][1]["admin"] is True


def test_agent_execution_rejected_without_atomic_gateway_budget(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_WEB_TASKS_ENABLED", "1")
    monkeypatch.setenv("DRAGONZPYDER_WEB_TASK_SERVICE_TOKEN", "s"*48)
    monkeypatch.setenv("DRAGONZPYDER_WEB_TASKS_PAID_ENABLED", "1")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_USE_GATEWAY", "1")
    import main
    with patch.object(main.parent_budget, "store", None):
        with TestClient(api()) as client:
            result = client.post("/internal/web-tasks/submit",
                headers={"Authorization": "Bearer " + "s"*48},
                json={"owner": "person@example.test", "request_id": str(uuid4()),
                      "kind": "agent", "goal": "Summarize a scientific paper"})
    assert result.status_code == 503
