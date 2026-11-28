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
            assert client.get("/admin", headers={"x-role": "admin"}, follow_redirects=False).status_code == 303
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


def test_operations_denies_unverified_and_legacy_only_sessions(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_ADMIN_EMAILS", "owner@example.test")
    with TestClient(app) as client:
        assert client.get("/admin/api/operations?source=github").status_code == 401
        old = client.app.state.http
        client.app.state.http = httpx.AsyncClient(transport=httpx.MockTransport(
            lambda req: httpx.Response(200, json={"email": "owner@example.test", "id": "admin-subject"})))
        try:
            assert client.get("/admin/api/operations?source=github",
                headers={"cookie": "__Host-operly_session=valid"}).status_code == 403
            assert client.get("/admin/api/operations?source=bogus",
                headers={"cookie": "__Host-dz_identity=valid"}).status_code == 400
        finally:
            client.app.state.http = old


def test_operations_traffic_summary_excludes_raw_paths_and_ips():
    result = main._admin_traffic_summary([
        {"path": "/api/private-user/secret?token=secret", "srcIp": "192.0.2.1",
         "httpStatus": 200, "edgeRegion": "us-west", "totalDuration": 15, "rxBytes": 20},
        {"path": "/", "httpStatus": 503, "edgeRegion": "us-west", "totalDuration": 50},
    ])
    assert result["routes"] == {"/api": 1, "/": 1}
    assert result["edge_regions"] == {"us-west": 2}
    assert result["p95_duration_ms"] == 50
    assert "secret" not in str(result) and "192.0.2.1" not in str(result)


def test_langfuse_operations_filters_provider_payload(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_ADMIN_EMAILS", "owner@example.test")
    monkeypatch.setenv("DRAGONZPYDER_ADMIN_LANGFUSE_HOST", "https://cloud.langfuse.com")
    monkeypatch.setenv("DRAGONZPYDER_ADMIN_LANGFUSE_PUBLIC_KEY", "public-test")
    monkeypatch.setenv("DRAGONZPYDER_ADMIN_LANGFUSE_SECRET_KEY", "secret-test")
    def upstream(req):
        if req.url.path == "/identity/v1/me":
            return httpx.Response(200, json={"email": "owner@example.test", "id": "admin-subject"})
        assert req.url.host == "cloud.langfuse.com"
        assert "io" not in req.url.params["fields"].split(",")
        assert req.headers.get("cookie") == ""
        return httpx.Response(200, json={"data": [{"traceId": "trace-1", "model": "example-model",
            "input": "private-prompt", "output": "private-answer", "userId": "private-user"}], "meta": {}})
    with TestClient(app) as client:
        old = client.app.state.http
        client.app.state.http = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
        try:
            r = client.get("/admin/api/operations?source=langfuse",
                headers={"cookie": "__Host-dz_identity=valid"})
            assert r.status_code == 200
            assert r.json()["observations"] == [{"traceId": "trace-1", "model": "example-model"}]
            assert "private-" not in r.text and "secret-test" not in r.text
            assert r.headers["cache-control"] == "no-store"
        finally:
            client.app.state.http = old


def test_activity_proxy_reuses_private_admin_token(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_ADMIN_EMAILS", "owner@example.test")
    token = "A" * 48
    monkeypatch.setenv("DRAGONZPYDER_ADMIN_TOKEN", token)
    def upstream(req):
        if req.url.path == "/identity/v1/me":
            return httpx.Response(200, json={"id":"admin-subject","email":"owner@example.test"})
        assert req.url.path == "/internal/admin/activity"
        assert req.headers["authorization"] == "Bearer " + token
        assert req.headers["cookie"] == ""
        assert req.url.params["days"] == "7"
        return httpx.Response(200, json={"days":7,"requests":{"state":"available","rows":[]}})
    with TestClient(app) as client:
        old = client.app.state.http
        client.app.state.http = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
        try:
            h = {"cookie":"__Host-dz_identity=valid"}
            result = client.get("/admin/api/operations?source=activity&days=7",headers=h)
            assert result.status_code == 200
            assert result.json()["activity"]["days"] == 7 and token not in result.text
            assert client.get("/admin/api/operations?source=activity&days=91",headers=h).status_code == 400
        finally:
            client.app.state.http = old


def test_resources_projection_filters_unknown_metrics_and_invalid_samples():
    data = main._admin_resource_summary([
        {"measurement":"CPU_USAGE","tags":{"serviceId":"service-1"},"values":[
            {"ts":10,"value":0.4,"private":"ignore"},
            {"ts":20,"value":0.6},
            {"ts":30,"value":-1},
        ]},
        {"measurement":"UNSUPPORTED","tags":{"serviceId":"service-1"},"values":[]},
        {"measurement":"MEMORY_USAGE_GB","tags":{"serviceId":"unknown"},"values":[]},
    ],{"service-1":"API"})
    assert len(data)==1 and data[0]["service"]=="API"
    assert data[0]["current"]==0.6 and data[0]["average"]==0.5
    assert "private" not in str(data) and "ignore" not in str(data)
    assert main._admin_metric_samples([{"ts":10,"value":float("inf")},{"ts":20,"value":1.0}]) == [{"ts":10},{"ts":20,"value":1.0}]


def test_traffic_client_classes_are_bounded_not_raw():
    data = main._admin_traffic_summary([
        {"clientUa": "Mozilla/5.0 (Linux; Android 14; private-device-id) Chrome/124.0 Mobile Safari/537.36"},
        {"clientUa": "Mozilla/5.0 (Windows NT 10.0) Chrome/124.0 Edg/124.0"},
        {"clientUa": "Mozilla/5.0 (iPhone) Version/17.0 Safari/604.1"},
        {"clientUa": "okhttp/4.12.0"}, {},
    ])
    assert data["devices"] == {"Phone": 2, "Desktop / laptop": 1, "Unknown": 2}
    assert data["operating_systems"] == {"Android": 1, "Windows": 1, "iOS": 1, "Unknown": 2}
    assert data["browsers"] == {"Chrome": 1, "Edge": 1, "Safari": 1, "Native HTTP client": 1, "Unknown": 1}
    assert "private-device-id" not in str(data)


def test_config_change_requires_native_csrf_and_fixed_flag(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_ADMIN_EMAILS", "owner@example.test")
    def upstream(req):
        assert req.url.path == "/identity/v1/me"
        return httpx.Response(200,json={"id":"admin-subject","email":"owner@example.test"})
    with TestClient(app) as client:
        old=client.app.state.http
        client.app.state.http=httpx.AsyncClient(transport=httpx.MockTransport(upstream))
        try:
            path="/admin/api/config"
            body={"service":"API","flag":"OPENROUTER_API_KEY","expected":"on","enabled":False,"confirm":True}
            h={"cookie":"__Host-dz_identity=valid; __Host-dz_csrf=test","origin":"https://dragonzpyder.xyz","x-dz-csrf":"test"}
            assert client.post(path,json=body,headers={"cookie":"__Host-dz_identity=valid"}).status_code==403
            assert client.post(path,json=body,headers=h).status_code==400
            assert client.post(path,json=body,headers={**h,"origin":"https://evil.test"}).status_code==403
            body["flag"]="DRAGONZPYDER_AGENT_WEB_SEARCH_ENABLED"
            monkeypatch.delenv("DRAGONZPYDER_ADMIN_RAILWAY_DRAGONZPYDER_TOKEN",raising=False)
            assert client.post(path,json=body,headers=h).status_code==503
        finally:
            client.app.state.http=old


def test_country_and_campaign_aggregates_are_not_raw():
    class Reader:
        def get(self, ip):
            return {"country":{"iso_code":"US"}}
    report=main._admin_traffic_summary([{"srcIp":"8.8.8.8","path":"/?utm_source=google&secret=private"}, {"srcIp":"127.0.0.1","path":"/?utm_source=private-identifier"}],Reader())
    assert report["countries"]=={"US":1,"Unknown":1}
    assert report["campaign_sources"]=={"google":1,"Other tagged source":1}
    assert "8.8.8.8" not in str(report) and "private" not in str(report)
    assert main._admin_traffic_summary([])["geo_state"]=="unconfigured"
