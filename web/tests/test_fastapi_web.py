import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from fastapi.testclient import TestClient

from main import app


def test_static_pages_and_source_not_exposed():
    with TestClient(app) as client:
        assert client.get("/healthz").json() == {"status": "ok", "service": "dragonzpyder-web"}
        for path in ("/app.js", "/mesh.js", "/app.css", "/account.css"):
            response = client.get(path)
            assert response.status_code == 200, path
        # Page content is served only from the React build, never old templates.
        for path in ("/", "/index.html", "/app", "/account"):
            response = client.get(path)
            assert response.status_code in (200, 503), path
        for path in ("/server.mjs", "/home.js", "/main.py", "/backend/security.py", "/package.json", "/random"):
            assert client.get(path).status_code == 404


def mock_backend(request):
    if request.url.path == "/api/auth/sessions":
        return httpx.Response(200, json=[{"id": "test-session", "scope": "personal", "current": True}])
    if request.url.path == "/api/personal-agent/chat":
        return httpx.Response(200, json={"ok": True}, headers=[("set-cookie", "a=1; Path=/"),
                                                                  ("set-cookie", "b=2; Path=/")])
    if request.url.path == "/internal/provider/models":
        return httpx.Response(200, json={"data": [
            {"id": "test/model", "name": "Test model",
             "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
             "pricing": {"prompt": "0.0000001", "completion": "0.0000001"}}]})
    if request.url.path == "/internal/provider/images/models" or request.url.path == "/internal/provider/videos/models":
        return httpx.Response(200, json={"data": []})
    if request.url.path == "/internal/provider/chat/completions":
        return httpx.Response(200, json={"id": "test", "choices": [
            {"message": {"content": "Hello from Python"}}], "usage": {"total_tokens": 4}})
    return httpx.Response(404)


def test_mesh_requires_personal_session_and_csrf(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_MESH_GATEWAY_TOKEN", "m" * 48)
    with TestClient(app) as client:
        real_http = client.app.state.http
        client.app.state.http = httpx.AsyncClient(transport=httpx.MockTransport(mock_backend))
        try:
            assert client.get("/mesh/models").status_code == 200
            assert client.post("/mesh/chat", json={"model": "test/model", "messages": [
                {"role": "user", "content": "hi"}]}).status_code == 403
            header = {"host": "testserver", "origin": "http://testserver",
                      "cookie": "operly_csrf=good", "x-csrf-token": "good"}
            # Production origin must be HTTPS; test origin is not an exception.
            assert client.post("/mesh/chat", headers=header, json={"model": "test/model", "messages": [
                {"role": "user", "content": "hi"}]}).status_code == 403
            header["origin"] = "http://localhost"
            header["host"] = "localhost"
            r = client.post("http://localhost/mesh/chat", headers=header, json={
                "model": "test/model", "messages": [{"role": "user", "content": "hi"}]})
            assert r.status_code == 200, r.text
            assert r.json()["text"] == "Hello from Python"
        finally:
            client.app.state.http = real_http


def test_api_proxy_preserves_cookies_and_origin():
    with TestClient(app) as client:
        real_http = client.app.state.http
        client.app.state.http = httpx.AsyncClient(transport=httpx.MockTransport(mock_backend))
        try:
            response = client.post("/api/personal-agent/chat", json={"message": "hi"})
            assert response.status_code == 200
            assert len(response.headers.get_list("set-cookie")) == 2
        finally:
            client.app.state.http = real_http


def test_compiled_react_pages_and_hashed_assets(monkeypatch, tmp_path):
    import main
    monkeypatch.setattr(main, "DIST", tmp_path)
    (tmp_path / "index.html").write_text("<h1>React home build</h1>", encoding="utf8")
    (tmp_path / "app.html").write_text("<h1>React chat build</h1>", encoding="utf8")
    (tmp_path / "account.html").write_text("<h1>React account build</h1>", encoding="utf8")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "main-abcd.js").write_text("console.log('react')", encoding="utf8")
    with TestClient(app) as client:
        assert "React home build" in client.get("/").text
        assert "React chat build" in client.get("/app").text
        assert "React account build" in client.get("/account").text
        js = client.get("/assets/main-abcd.js")
        assert js.status_code == 200
        assert "immutable" in js.headers["cache-control"]
        assert client.get("/assets/no-file.js").status_code == 404
        assert client.get("/main.py").status_code == 404


def test_legacy_html_urls_redirect_to_clean_react_pages():
    with TestClient(app) as client:
        for old, new in (("/app.html", "/app"), ("/account.html", "/account")):
            response = client.get(old, follow_redirects=False)
            assert response.status_code == 308
            assert response.headers["location"] == new
            assert response.headers["cache-control"] == "no-store"
        response = client.get("/account.html?mode=signup&next=profile", follow_redirects=False)
        assert response.status_code == 308
        assert response.headers["location"] == "/account?mode=signup&next=profile"
        assert client.get("/app", follow_redirects=False).status_code in (200, 503)
        assert client.get("/account", follow_redirects=False).status_code in (200, 503)
        assert client.get("/app", headers={"host": "chat.dragonspire.xyz"},
                          follow_redirects=False).status_code == 404
