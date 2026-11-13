"""No-inference service-auth contract for DragonZpyder's persistent goals."""
from uuid import uuid4
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_platform.goal_router import router


class FakeStore:
    def __init__(self):
        self.calls = []

    async def register(self, **kwargs):
        self.calls.append(("register", kwargs))
        return {"goal_id": "synthetic", "status": "registered",
                "execution_started": False, "job_registered": False,
                "requires_fresh_authorization": True}

    async def cancel(self, **kwargs):
        self.calls.append(("cancel", kwargs))
        return {"goal_id": kwargs["goal_id"], "status": "cancelled"}

    async def get(self, **kwargs):
        self.calls.append(("get", kwargs))
        return {"goal_id": kwargs["goal_id"], "status": "registered"}


def app():
    api = FastAPI()
    api.include_router(router)
    api.state.goal_store = FakeStore()
    return api


def test_goal_api_feature_disabled_by_default(monkeypatch):
    monkeypatch.delenv("DRAGONZPYDER_GOAL_STORE_ENABLED", raising=False)
    with TestClient(app()) as client:
        x = client.post("/internal/goals/register",
            json={"kind":"personal","user_id":"test-user","workspace_id":None,
                  "request_id":str(uuid4()),"goal":"Test without authorization"})
    assert x.status_code == 503


def test_goal_api_requires_dedicated_service_credential(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_GOAL_STORE_ENABLED", "1")
    monkeypatch.setenv("DRAGONZPYDER_OPERLY_AGENT_TOKEN", "g" * 48)
    with TestClient(app()) as client:
        x = client.post("/internal/goals/register",
            json={"kind":"personal","user_id":"test-user","workspace_id":None,
                  "request_id":str(uuid4()),"goal":"Test without authorization"})
    assert x.status_code == 401


def test_goal_record_scoped_to_authenticated_service(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_GOAL_STORE_ENABLED", "1")
    monkeypatch.setenv("DRAGONZPYDER_OPERLY_AGENT_TOKEN", "g" * 48)
    api = app()
    with TestClient(api) as client:
        x = client.post("/internal/goals/register",
            headers={"Authorization": "Bearer " + "g"*48},
            json={"kind":"workspace", "user_id":"alice",
                  "workspace_id":"business-1", "request_id":str(uuid4()),
                  "goal":"Monitor product issues",
                  "schedule":{"type":"cron","expression":"0 9 * * 1","timezone":"UTC"}})
    assert x.status_code == 200, x.text
    assert x.json()["execution_started"] is False
    assert x.json()["job_registered"] is False
    assert api.state.goal_store.calls[0][1]["source_app"] == "operly"
    assert api.state.goal_store.calls[0][1]["workspace_id"] == "business-1"
