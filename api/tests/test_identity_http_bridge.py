"""HTTP bridge gates tested offline with no external database or providers."""
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlencode, urlsplit, parse_qs

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import identity.http_bridge as bridge
from identity.grants import AuthorizationGrant, RedeemedGrant
from datetime import datetime, timedelta, timezone

app = FastAPI()
app.include_router(bridge.router)
ISSUER = "https://api.dragonzpyder.xyz"
REDIRECT = "https://operly.dragonzpyder.xyz/auth/callback"
CHALLENGE = "a" * 43


@pytest.fixture(autouse=True)
def disabled_by_default(monkeypatch):
    monkeypatch.delenv("DRAGONZPYDER_IDENTITY_HTTP_ENABLED", raising=False)
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "staging")
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_ISSUER", ISSUER)


def payload():
    return {"response_type": "code", "client_id": "operly-web", "redirect_uri": REDIRECT,
            "scope": "operly:access", "state": "opaque-state-value-1234",
            "code_challenge_method": "S256", "code_challenge": CHALLENGE}


def test_auth_endpoints_unavailable_without_opt_in():
    with TestClient(app) as c:
        assert c.post("/identity/v1/authorize", json=payload()).status_code == 404
        assert c.post("/identity/v1/token", data={"grant_type": "authorization_code"}).status_code == 404


def test_auth_is_explicitly_blocked_in_production(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_HTTP_ENABLED", "1")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "production")
    with TestClient(app) as c:
        assert c.post("/identity/v1/authorize", json=payload()).status_code == 503


def test_authorize_rejects_cross_origin_and_non_pkce(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_HTTP_ENABLED", "1")
    with TestClient(app) as c:
        assert c.post("/identity/v1/authorize", json=payload(), headers={"Origin": "https://evil.example"}).status_code == 403
        wrong = {**payload(), "code_challenge_method": "plain"}
        assert c.post("/identity/v1/authorize", json=wrong, headers={"Origin": ISSUER}).status_code == 400


def test_authorize_requires_real_session_and_safely_redirects(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_HTTP_ENABLED", "1")
    @asynccontextmanager
    async def db():
        yield object()
    monkeypatch.setattr(bridge, "_identity_db", db)
    async def authenticate(db, *, secret, csrf, require_csrf):
        assert require_csrf
        assert secret == "session-secret"
        assert csrf == "csrf-secret"
        return "existing-operly-user"
    async def issue(db, **kwargs):
        assert kwargs["authenticated_subject"] == "existing-operly-user"
        assert kwargs["pkce_s256"] == CHALLENGE
        return AuthorizationGrant(code="single-use-secret", expires_at=datetime.now(timezone.utc) + timedelta(seconds=90))
    monkeypatch.setattr(bridge, "resolve_browser_session", authenticate)
    monkeypatch.setattr(bridge, "authorize_code", issue)
    with TestClient(app) as c:
        c.cookies.set("__Host-dz_identity", "session-secret")
        resp = c.post("/identity/v1/authorize", json=payload(),
                      headers={"Origin": ISSUER, "x-dz-csrf": "csrf-secret"}, follow_redirects=False)
        assert resp.status_code == 303
        uri = urlsplit(resp.headers["location"])
        assert uri.scheme == "https" and uri.netloc == "operly.dragonzpyder.xyz"
        assert parse_qs(uri.query) == {"code": ["single-use-secret"], "state": ["opaque-state-value-1234"]}


def test_token_endpoint_rejects_json_and_duplicate_form_fields(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_HTTP_ENABLED", "1")
    with TestClient(app) as c:
        assert c.post("/identity/v1/token", json={"grant_type": "authorization_code"}).status_code == 415
        raw = "grant_type=authorization_code&grant_type=password"
        assert c.post("/identity/v1/token", content=raw, headers={"content-type": "application/x-www-form-urlencoded"}).status_code == 400


def test_valid_code_token_exchange_never_trusts_request_subject(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_HTTP_ENABLED", "1")
    @asynccontextmanager
    async def db():
        yield object()
    class DummyIssuer:
        @classmethod
        def from_environment(cls):
            return cls()
        def issue_access_token(self, *, authenticated_subject, audience, scope):
            assert (authenticated_subject, audience, scope) == ("trusted-subject", "operly-api", "operly:access")
            return "signed-synthetic-token"
    async def exchange(db, signer, **kwargs):
        assert kwargs["client_id"] == "operly-web"
        return {"access_token": "signed-synthetic-token", "token_type": "Bearer",
                "expires_in": 300, "scope": "operly:access"}
    monkeypatch.setattr(bridge, "_identity_db", db)
    monkeypatch.setattr(bridge, "SigningIdentity", DummyIssuer)
    monkeypatch.setattr(bridge, "exchange_code", exchange)
    body = {"grant_type": "authorization_code", "client_id": "operly-web",
            "redirect_uri": REDIRECT, "code": "synthetic-secret", "code_verifier": "v" * 50}
    with TestClient(app) as c:
        result = c.post("/identity/v1/token", data=body)
        assert result.status_code == 200
        assert result.json() == {"access_token": "signed-synthetic-token", "token_type": "Bearer", "expires_in": 300, "scope": "operly:access"}
        assert result.headers["cache-control"] == "no-store"
