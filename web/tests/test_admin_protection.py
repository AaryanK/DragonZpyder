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
            if request.headers.get("cookie") == "__Host-operly_session=valid":
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
            h = {"cookie": "__Host-operly_session=valid"}
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


def test_signed_out_admin_page_redirects_to_first_party_login(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_ADMIN_EMAILS", "owner@example.test")
    with TestClient(app) as client:
        response = client.get("/admin", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/account?next=%2Fadmin"
        assert response.headers["cache-control"] == "no-store"
        api = client.get("/admin/api/usage")
        assert api.status_code == 401
        assert api.headers["cache-control"] == "no-store"
        # No arbitrary forwarding target may be supplied by an attacker.
        suspicious = client.get("/admin?next=https://attacker.test", follow_redirects=False)
        assert suspicious.headers["location"] == "/account?next=%2Fadmin"


def test_expired_session_redirects_and_wrong_account_denied(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_ADMIN_EMAILS", "owner@example.test")

    def upstream(request):
        if request.headers.get("cookie") == "__Host-operly_session=expired":
            return httpx.Response(401, json={"detail": "Session expired"})
        return httpx.Response(200, json={"email": "someone-else@example.test"})

    with TestClient(app) as client:
        old = client.app.state.http
        client.app.state.http = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
        try:
            expired = client.get("/admin", headers={"cookie": "__Host-operly_session=expired"},
                                 follow_redirects=False)
            assert expired.status_code == 303
            assert expired.headers["location"] == "/account?next=%2Fadmin"
            wrong = client.get("/admin", headers={"cookie": "__Host-operly_session=valid"},
                               follow_redirects=False)
            assert wrong.status_code == 403
            assert "text/html" in wrong.headers["content-type"]
            assert "not on the administrator allowlist" in wrong.text
            assert "owner@example.test" not in wrong.text
            api = client.get("/admin/api/usage", headers={"cookie": "__Host-operly_session=valid"})
            assert api.status_code == 403
        finally:
            client.app.state.http = old


def test_unavailable_identity_service_cannot_authorize_admin(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_ADMIN_EMAILS", "owner@example.test")

    def upstream(request):
        return httpx.Response(502, json={"detail": "Temporary upstream outage"})

    with TestClient(app) as client:
        old = client.app.state.http
        client.app.state.http = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
        try:
            response = client.get("/admin", headers={"cookie": "__Host-operly_session=valid"})
            assert response.status_code == 503
            assert "temporarily unavailable" in response.text
            assert client.get("/admin/api/usage",
                       headers={"cookie": "__Host-operly_session=valid"}).status_code == 503
        finally:
            client.app.state.http = old


def test_account_redirect_only_allows_admin_return():
    script = (Path(__file__).resolve().parents[1] / "account.js").read_text()
    assert 'get("next")==="/admin"' in script
    assert 'window.location.replace(adminReturnRequested()?"/admin":"/app")' in script
