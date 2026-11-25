"""Native DragonZpyder browser proxy must be explicitly scoped and CSRF-safe."""
import sys
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from main import app


def test_native_proxy_is_not_a_general_internal_gateway(monkeypatch):
    calls = []
    def handler(request):
        calls.append((request.method, str(request.url), request.headers.get("origin"),
                      request.headers.get("cookie")))
        return httpx.Response(
            200, json={"ok": True}, headers={"set-cookie": "__Host-dz_identity=opaque; Secure; Path=/; HttpOnly"},
        )
    with TestClient(app, base_url="https://www.dragonzpyder.xyz") as client:
        original = client.app.state.http
        client.app.state.http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            for path in (
                "/dz/internal/agents/run",
                "/dz/internal/agents/operly/personal/run",
                "/dz/internal/v1/chat/completions",
                "/dz/identity/v1/token",
            ):
                assert client.post(path).status_code == 404
            assert calls == []
            assert client.post(
                "/dz/v2/personal/chat", json={"message": "hello"},
                headers={"origin": "https://attacker.invalid"},
            ).status_code == 403
            assert calls == []
            ok = client.post(
                "/dz/v2/personal/chat",
                headers={"origin": "https://www.dragonzpyder.xyz",
                         "cookie": "__Host-dz_identity=opaque",
                         "x-dz-csrf": "csrf"},
                json={"message": "hello"},
            )
            assert ok.status_code == 200
            assert len(calls) == 1
            method, url, origin, cookie = calls[0]
            assert method == "POST"
            assert url == "https://api.dragonzpyder.xyz/v2/personal/chat"
            assert origin == "https://api.dragonzpyder.xyz"
            assert "__Host-dz_identity=opaque" in cookie
            assert ok.headers["set-cookie"].startswith("__Host-dz_identity=")
        finally:
            client.app.state.http = original


def test_web_cutover_requires_explicit_flag(monkeypatch):
    monkeypatch.delenv("DRAGONZPYDER_FIRST_PARTY_WEB_CUTOVER_ENABLED", raising=False)
    with TestClient(app) as client:
        assert client.get("/dz/status").json() == {"web_cutover_enabled": False}
        monkeypatch.setenv("DRAGONZPYDER_FIRST_PARTY_WEB_CUTOVER_ENABLED", "1")
        assert client.get("/dz/status").json() == {"web_cutover_enabled": True}


def test_native_cutover_never_uses_operly_mesh_voice_or_legacy_auth(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_FIRST_PARTY_WEB_CUTOVER_ENABLED", "1")
    upstream = []
    def handler(request):
        upstream.append(str(request.url))
        return httpx.Response(200, json={"ok": True})
    with TestClient(app, base_url="https://www.dragonzpyder.xyz") as client:
        original = client.app.state.http
        client.app.state.http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            for route in [
                "/api/auth/login", "/api/personal-agent/chat",
                "/api/personal-tools", "/api/agent/chat",
            ]:
                assert client.post(route).status_code == 410
            assert client.get("/mesh/models").status_code == 503
            assert client.get("/companion/realtime").status_code == 503
            assert upstream == [], "Native cutover must not contact legacy Operly."
            response = client.post("/dz/identity/v1/provider/google/start",
                headers={"origin": "https://www.dragonzpyder.xyz"})
            assert response.status_code == 200
            assert upstream == ["https://api.dragonzpyder.xyz/identity/v1/provider/google/start"]
        finally:
            client.app.state.http = original


def test_migration_proof_proxy_is_separately_gated_and_exact(monkeypatch):
    calls = []
    def handler(request):
        calls.append((request.method, str(request.url), request.headers.get("origin")))
        return httpx.Response(202,json={"status":"awaiting_review"})
    monkeypatch.delenv("DRAGONZPYDER_IMPORT_PROOF_WEB_ENABLED",raising=False)
    monkeypatch.delenv("DRAGONZPYDER_FIRST_PARTY_WEB_CUTOVER_ENABLED",raising=False)
    with TestClient(app,base_url="https://www.dragonzpyder.xyz") as client:
        original=client.app.state.http
        client.app.state.http=httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            root="/dz/identity/v1/import-proof"
            origin={"origin":"https://www.dragonzpyder.xyz"}
            assert client.get("/dz/import-proof/status").json()=={"enabled":False}
            assert client.post(root+"/password",headers=origin,json={}).status_code==404
            monkeypatch.setenv("DRAGONZPYDER_IMPORT_PROOF_WEB_ENABLED","1")
            assert client.get("/dz/import-proof/status").json()=={"enabled":True}
            assert client.get("/dz/status").json()=={"web_cutover_enabled":False}
            assert client.get(root+"/password").status_code==404
            assert client.post(root+"/approve",headers=origin).status_code==404
            assert client.post(root+"/password",headers={"origin":"https://evil.invalid"},json={}).status_code==403
            assert calls==[]
            assert client.post(root+"/password",headers=origin,json={}).status_code==202
            assert calls==[("POST","https://api.dragonzpyder.xyz/identity/v1/import-proof/password","https://api.dragonzpyder.xyz")]
        finally:
            client.app.state.http=original


def test_proof_proxy_never_relays_legacy_or_native_session_credentials(monkeypatch):
    calls=[]
    def handler(request):
        calls.append((request.headers.get("cookie"),request.headers.get("authorization"),
                      request.headers.get("x-csrf-token")))
        return httpx.Response(202,json={"status":"awaiting_review"},headers=[
            ("set-cookie","__Host-dz_import_proof="+"p"*48+"; Secure; Path=/; HttpOnly"),
            ("set-cookie","__Host-dz_identity=must-not-relay; Secure; Path=/; HttpOnly"),
        ])
    monkeypatch.setenv("DRAGONZPYDER_IMPORT_PROOF_WEB_ENABLED","1")
    with TestClient(app,base_url="https://www.dragonzpyder.xyz") as client:
        original=client.app.state.http
        client.app.state.http=httpx.AsyncClient(transport=httpx.MockTransport(handler),
                                                cookies=original.cookies)
        try:
            path="/dz/identity/v1/import-proof/google/complete"
            origin={"origin":"https://www.dragonzpyder.xyz"}
            assert client.post(path+"?secret=x",headers=origin).status_code==400
            assert client.post(path,headers=origin,content=b"x"*12289).status_code==413
            response=client.post(path,headers={**origin,
                "cookie":"__Host-operly_session=legacy; __Host-dz_identity=native; __Host-dz_import_proof="+"a"*48,
                "authorization":"Bearer unwanted","x-csrf-token":"legacy-csrf"},json={})
            assert response.status_code==202
            assert calls==[("__Host-dz_import_proof="+"a"*48,None,None)]
            assert len(response.headers.get_list("set-cookie"))==1
            assert response.headers["set-cookie"].startswith("__Host-dz_import_proof=")
            assert list(client.app.state.http.cookies.jar)==[]
            client.cookies.clear()
            assert client.post(path,headers=origin,json={}).status_code==202
            assert calls[-1]==("",None,None)
        finally:
            client.app.state.http=original
