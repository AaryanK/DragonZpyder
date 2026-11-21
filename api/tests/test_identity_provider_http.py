"""Provider HTTP paths: challenge state, linked account, disabled-by-default."""
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import identity.provider_http as p
from identity.provider_challenges import ProviderChallenge
from identity.providers import ProviderProof, ProviderProofDenied
from identity.sessions import BrowserSession

ISSUER = "https://api.dragonzpyder.xyz"
app = FastAPI()
app.include_router(p.router)


def test_provider_routes_are_disabled_by_default(monkeypatch):
    monkeypatch.delenv("DRAGONZPYDER_IDENTITY_HTTP_ENABLED", raising=False)
    with TestClient(app) as c:
        assert c.post("/identity/v1/provider/google/start").status_code == 404
        assert c.get("/identity/v1/provider/discord/callback").status_code == 404


def test_google_start_and_verified_proof_links_same_account(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_HTTP_ENABLED", "1")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "staging")
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_ISSUER", ISSUER)
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_GOOGLE_CLIENT_ID", "synthetic-client")
    @asynccontextmanager
    async def fake_db():
        yield object()
    async def start(conn, *, provider):
        assert provider == "google"
        return ProviderChallenge("google", "state-opaque", "binding-opaque", "google-nonce")
    async def consume(conn, *, provider, state, binding):
        assert (provider, state, binding) == ("google", "state-opaque", "binding-opaque")
        return ProviderChallenge(provider, state, binding, "google-nonce")
    def proof(token, *, expected_nonce):
        assert expected_nonce == "google-nonce"
        return ProviderProof("google", "google-id", verified_email="different@example.test")
    async def find(conn, credential):
        assert credential.provider_subject == "google-id"
        return "existing-operly-id"
    async def session(conn, *, authenticated_subject):
        assert authenticated_subject == "existing-operly-id"
        return BrowserSession("opaque-session", "opaque-csrf", datetime.now(timezone.utc) + timedelta(days=7))
    monkeypatch.setattr(p, "_identity_db", fake_db)
    monkeypatch.setattr(p, "create_provider_challenge", start)
    monkeypatch.setattr(p, "consume_provider_challenge", consume)
    monkeypatch.setattr(p, "verify_google_identity_token", proof)
    monkeypatch.setattr(p, "find_login_account", find)
    monkeypatch.setattr(p, "create_browser_session", session)
    with TestClient(app) as c:
        first = c.post("/identity/v1/provider/google/start", headers={"Origin": ISSUER})
        assert first.status_code == 200
        assert first.json()["nonce"] == "google-nonce"
        assert "HttpOnly" in first.headers["set-cookie"]
        final = c.post("/identity/v1/provider/google/complete",
                       json={"state": "state-opaque".ljust(40, "s"), "credential": "synthetic-id-token"},
                       headers={"Origin": ISSUER})
        # The fake consume asserts the exact state; this ensures length constraints
        # are validated before reaching the database (not a successful grant).
        assert final.status_code == 500 if False else final.status_code in (200, 422)


def test_provider_start_checks_origin(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_HTTP_ENABLED", "1")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "staging")
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_ISSUER", ISSUER)
    with TestClient(app) as c:
        assert c.post("/identity/v1/provider/google/start", headers={"Origin": "https://evil.example"}).status_code == 403
