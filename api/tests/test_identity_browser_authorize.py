"""Browser authorization and OIDC discovery contracts, no real users."""
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from urllib.parse import urlencode, urlsplit

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import identity.browser_authorize as browser
import identity.http_bridge as bridge
from identity.router import router as discovery_router
from identity.sessions import SessionDenied
from identity.grants import AuthorizationGrant
from datetime import datetime, timezone, timedelta

ISSUER = "https://api.dragonzpyder.xyz"
REDIRECT = "https://operly.dragonzpyder.xyz/api/auth/dragonzpyder/callback"


def query():
    return {
        "response_type": "code", "client_id": "operly-web",
        "redirect_uri": REDIRECT, "scope": "openid operly:access",
        "state": "s" * 48, "nonce": "n" * 40,
        "code_challenge_method": "S256", "code_challenge": "c" * 43,
    }


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_ISSUER", ISSUER)
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "staging")
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_HTTP_ENABLED", "1")
    @asynccontextmanager
    async def db():
        yield object()
    async def client(conn, **kwargs):
        assert kwargs["client_id"] == "operly-web"
        assert kwargs["redirect_uri"] == REDIRECT
        return {"client_id": "operly-web", "audience": "operly-api"}
    async def no_session(conn, **kwargs):
        raise SessionDenied("not signed in")
    monkeypatch.setattr(browser.bridge, "_identity_db", db)
    monkeypatch.setattr(browser, "_registered_client", client)
    monkeypatch.setattr(browser, "resolve_browser_session", no_session)
    gateway = FastAPI()
    gateway.include_router(browser.router)
    gateway.include_router(bridge.router)
    gateway.include_router(discovery_router)
    return gateway


def test_get_authorize_shows_login_without_leaking_client_secrets(app):
    with TestClient(app, base_url=ISSUER) as c:
        response = c.get("/identity/v1/authorize?" + urlencode(query()))
    assert response.status_code == 200
    assert '<form id="login-form" method="post" action="/identity/v1/password/login"' in response.text
    assert '<fieldset id="login-fields" disabled>' in response.text
    assert "<noscript>" in response.text
    assert "consent" in response.text
    assert "hidden" in response.text
    assert "openid operly:access" in response.text
    assert "s" * 48 not in response.text
    assert "n" * 40 not in response.text
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert response.headers["referrer-policy"] == "no-referrer"


def test_authorize_rejects_duplicates_bad_scopes_and_unregistered_redirect(app, monkeypatch):
    async def reject_client(conn, **kwargs):
        from identity.grants import OAuthGrantDenied
        raise OAuthGrantDenied("not registered")
    with TestClient(app, base_url=ISSUER) as c:
        good = "/identity/v1/authorize?" + urlencode(query())
        assert c.get(good + "&client_id=impostor").status_code == 400
        bad = dict(query(), nonce="weak")
        assert c.get("/identity/v1/authorize?" + urlencode(bad)).status_code == 400
        monkeypatch.setattr(browser, "_registered_client", reject_client)
        assert c.get(good).status_code == 403


def test_consented_post_returns_json_url_for_same_origin_fetch(app, monkeypatch):
    async def session(conn, **kwargs):
        assert kwargs["require_csrf"] is True
        assert kwargs["csrf"] == "synthetic-csrf"
        return "existing-user"
    async def grant(conn, **kwargs):
        assert kwargs["authenticated_subject"] == "existing-user"
        assert kwargs["nonce"] == "n" * 40
        return AuthorizationGrant("one-time-code", datetime.now(timezone.utc) + timedelta(seconds=90))
    monkeypatch.setattr(bridge, "resolve_browser_session", session)
    monkeypatch.setattr(bridge, "authorize_code", grant)
    with TestClient(app, base_url=ISSUER) as c:
        response = c.post("/identity/v1/authorize", json=query(),
                          headers={"Origin": ISSUER, "x-dz-csrf": "synthetic-csrf",
                                   "Accept": "application/json"}, follow_redirects=False)
    assert response.status_code == 200
    redirect = urlsplit(response.json()["redirect_url"])
    assert redirect.netloc == "operly.dragonzpyder.xyz"
    assert response.headers["cache-control"] == "no-store"


def test_discovery_off_by_default_and_lists_actual_routes(monkeypatch, app):
    monkeypatch.delenv("DRAGONZPYDER_IDENTITY_JWKS_ENABLED", raising=False)
    with TestClient(app, base_url=ISSUER) as c:
        assert c.get("/.well-known/openid-configuration").status_code == 404
    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode()
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_SIGNING_KID", "synthetic-kid")
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_SIGNING_KEY_PEM", pem)
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_JWKS_ENABLED", "1")
    with TestClient(app, base_url=ISSUER) as c:
        discovery = c.get("/.well-known/openid-configuration")
    assert discovery.status_code == 200
    config = discovery.json()
    assert config["issuer"] == ISSUER
    assert config["authorization_endpoint"] == ISSUER + "/identity/v1/authorize"
    assert config["token_endpoint"] == ISSUER + "/identity/v1/token"
    assert config["jwks_uri"] == ISSUER + "/.well-known/jwks.json"
    assert config["code_challenge_methods_supported"] == ["S256"]
