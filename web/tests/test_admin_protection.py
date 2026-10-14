"""Admin must not be exposed by a browser-controlled role or cookie."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from fastapi.testclient import TestClient

import main
from main import app


def test_admin_denied_without_allowlist(monkeypatch, tmp_path):
    monkeypatch.delenv("DRAGONZPYDER_ADMIN_EMAILS", raising=False)
    (tmp_path / "admin.html").write_text("<h1>Private admin</h1>")
    monkeypatch.setattr(main, "DIST", tmp_path)
    with TestClient(app) as client:
        assert client.get("/admin").status_code == 403
        assert client.get("/admin/api/usage").status_code == 403


def test_admin_requires_verified_operly_identity_and_keeps_token_secret(monkeypatch, tmp_path):
    monkeypatch.setenv("DRAGONZPYDER_ADMIN_EMAILS", "owner@example.test")
    monkeypatch.setenv("DRAGONZPYDER_ADMIN_TOKEN", "A" * 48)
    (tmp_path / "admin.html").write_text("<h1>Private admin</h1>")
    monkeypatch.setattr(main, "DIST", tmp_path)
    calls = []

    def service(request):
        calls.append(request)
        if request.url.path == "/api/auth/me":
            if request.headers.get("cookie") == "session=valid":
                return httpx.Response(200, json={"email": "OWNER@example.test"})
            return httpx.Response(401, json={"detail": "Unauthorized"})
        if request.url.path == "/internal/admin/usage":
            assert request.headers["authorization"] == "Bearer " + "A" * 48
            return httpx.Response(200, json={"totals": {"calls": 3}, "groups": []})
        return httpx.Response(404)

    with TestClient(app) as client:
        original = client.app.state.http
        client.app.state.http = httpx.AsyncClient(transport=httpx.MockTransport(service))
        try:
            assert client.get("/admin", headers={"x-role": "admin"}).status_code == 403
            h = {"cookie": "session=valid"}
            response = client.get("/admin", headers=h)
            assert response.status_code == 200
            assert "Private admin" in response.text
            assert response.headers["cache-control"] == "no-store"
            data = client.get("/admin/api/usage?days=7", headers=h)
            assert data.status_code == 200
            assert data.json()["totals"]["calls"] == 3
            assert "A" * 48 not in data.text
            assert client.get("/admin/api/usage?days=0", headers=h).status_code == 400
            assert client.get("/admin", headers={**h, "host": "chat.dragonspire.xyz"}).status_code == 404
        finally:
            client.app.state.http = original
