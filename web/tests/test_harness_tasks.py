"""Browser task routing: Personal session + CSRF + scoped admin control."""
import sys
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main

OWNER = "account-one@example.test"
TOKEN = "S" * 48
CSRF = "good_token_0123456789"


def backend(req):
    if req.url.path == "/api/auth/me":
        if "operly_session=valid" in req.headers.get("cookie", ""):
            return httpx.Response(200, json={"email": OWNER, "id": "user-1"})
        return httpx.Response(401)
    if req.url.path == "/api/auth/sessions":
        return httpx.Response(200, json=[
            {"id": "s", "current": True, "scope": "personal"}
        ])
    if req.url.path.startswith("/internal/web-tasks/"):
        assert req.headers.get("authorization") == "Bearer " + TOKEN
        data = __import__("json").loads(req.content or b"{}")
        if req.url.path.endswith("/submit"):
            assert data["owner"] == "user-1"
            assert "user_id" not in data
            return httpx.Response(200, json={
                "task_id": "00000000-0000-0000-0000-000000000001",
                "status": "queued", "kind": data["kind"],
            })
        if req.url.path.endswith("/list"):
            assert data == {"owner": "user-1"}
            return httpx.Response(200, json={"tasks": []})
        if req.url.path.endswith("/detail"):
            assert data["owner"] == "user-1"
            return httpx.Response(200, json={
                "task_id": data["task_id"], "status": "completed",
                "events": [{"event_id": 1, "kind": "completed",
                            "message": "Task completed", "at": "2026-11-09T12:00:00Z"}],
            })
        if req.url.path.endswith("/admin/list"):
            return httpx.Response(200, json={"tasks": [{"task_id": "synthetic", "status": "running"}]})
        if req.url.path.endswith("/admin/detail"):
            return httpx.Response(200, json={
                "task_id": data["task_id"], "status": "running", "events": [],
            })
    return httpx.Response(404)


def setup(monkeypatch, client):
    monkeypatch.setenv("DRAGONZPYDER_WEB_TASK_SERVICE_TOKEN", TOKEN)
    monkeypatch.setenv("DRAGONZPYDER_ADMIN_EMAILS", OWNER)
    previous = client.app.state.http
    client.app.state.http = httpx.AsyncClient(transport=httpx.MockTransport(backend))
    return previous


def auth_headers(*, csrf=True):
    cookies = "operly_session=valid; operly_csrf=" + CSRF
    return {
        "cookie": cookies,
        **({"x-csrf-token": CSRF} if csrf else {}),
    }


def test_browser_harness_requires_identity_scope_and_csrf(monkeypatch):
    with TestClient(main.app) as client:
        prior = setup(monkeypatch, client)
        try:
            assert client.get("/api/harness/tasks").status_code == 401
            assert client.post("/api/harness/tasks",
                headers=auth_headers(csrf=False),
                json={"request_id": str(uuid4()), "kind": "probe", "goal": "Test"}).status_code == 403
            assert client.get("/api/harness/tasks", headers=auth_headers()).status_code == 200
            result = client.post("/api/harness/tasks", headers=auth_headers(),
                json={"request_id": str(uuid4()), "kind": "probe", "goal": "Test Hatchet"})
            assert result.status_code == 200, result.text
            assert result.json()["kind"] == "probe"
            detail = client.get("/api/harness/tasks/00000000-0000-0000-0000-000000000001",
                headers=auth_headers())
            assert detail.status_code == 200
            assert detail.json()["events"][0]["kind"] == "completed"
        finally:
            client.app.state.http = prior


def test_non_admin_cannot_read_cross_user_operations(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_ADMIN_EMAILS", "different@example.test")
    with TestClient(main.app) as client:
        prior = setup(monkeypatch, client)
        try:
            monkeypatch.setenv("DRAGONZPYDER_ADMIN_EMAILS", "different@example.test")
            assert client.get("/admin/api/tasks", headers=auth_headers()).status_code == 403
            assert client.get("/admin/api/tasks/00000000-0000-0000-0000-000000000001",
                headers=auth_headers()).status_code == 403
        finally:
            client.app.state.http = prior


def test_admin_logs_do_not_include_user_prompts(monkeypatch):
    with TestClient(main.app) as client:
        prior = setup(monkeypatch, client)
        try:
            result = client.get("/admin/api/tasks", headers=auth_headers())
            assert result.status_code == 200, result.text
            assert "tasks" in result.json()
            assert TOKEN not in result.text
        finally:
            client.app.state.http = prior


def test_chat_hostname_cannot_query_private_harness(monkeypatch):
    with TestClient(main.app) as client:
        prior = setup(monkeypatch, client)
        try:
            result = client.get("/api/harness/tasks",
                headers={**auth_headers(), "host": "chat.dragonspire.xyz"})
            assert result.status_code == 404
        finally:
            client.app.state.http = prior
