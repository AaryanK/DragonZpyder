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
    with TestClient(app, base_url=ISSUER) as c:
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
        return ProviderChallenge("google", ("s" * 48), ("b" * 48), "google-nonce")
    async def consume(conn, *, provider, state, binding):
        assert (provider, state, binding) == ("google", ("s" * 48), ("b" * 48))
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
    with TestClient(app, base_url=ISSUER) as c:
        first = c.post("/identity/v1/provider/google/start", headers={"Origin": ISSUER})
        assert first.status_code == 200
        assert first.json()["nonce"] == "google-nonce"
        assert "HttpOnly" in first.headers["set-cookie"]
        final = c.post("/identity/v1/provider/google/complete",
                       json={"state": ("s" * 48).ljust(40, "s"), "credential": "synthetic-id-token"},
                       headers={"Origin": ISSUER})
        assert final.status_code == 200
        assert final.json()["authenticated"] is True
        assert "__Host-dz_identity" in final.headers["set-cookie"]


def test_provider_start_checks_origin(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_HTTP_ENABLED", "1")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "staging")
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_ISSUER", ISSUER)
    with TestClient(app, base_url=ISSUER) as c:
        assert c.post("/identity/v1/provider/google/start", headers={"Origin": "https://evil.example"}).status_code == 403



def test_google_signup_uses_explicit_verified_proof_and_never_merges_email(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_HTTP_ENABLED", "1")
    monkeypatch.setenv("DRAGONZPYDER_NATIVE_GOOGLE_SIGNUP_ENABLED", "1")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "staging")
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_ISSUER", ISSUER)
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_GOOGLE_CLIENT_ID", "verified-client")
    @asynccontextmanager
    async def fake_db():
        yield object()
    async def start(conn, *, provider):
        return ProviderChallenge("google", ("s" * 48), ("b" * 48), "google-nonce")
    async def consume(conn, *, provider, state, binding):
        assert state == "s" * 48 and binding == "b" * 48
        return ProviderChallenge("google", state, binding, "google-nonce")
    def verified(token, *, expected_nonce):
        assert (token, expected_nonce) == ("id-token", "google-nonce")
        return ProviderProof("google", "verified-google-sub", "owner@example.test")
    async def signup(conn, proof):
        assert proof.provider_subject == "verified-google-sub"
        assert proof.verified_email == "owner@example.test"
        return "native-user-id"
    async def no_legacy_lookup(conn, proof):
        raise AssertionError("Signup cannot link to an existing Operly account")
    async def session(conn, *, authenticated_subject):
        assert authenticated_subject == "native-user-id"
        return BrowserSession("opaque-session", "opaque-csrf",
                              datetime.now(timezone.utc) + timedelta(days=7))
    monkeypatch.setattr(p, "_identity_db", fake_db)
    monkeypatch.setattr(p, "create_provider_challenge", start)
    monkeypatch.setattr(p, "consume_provider_challenge", consume)
    monkeypatch.setattr(p, "verify_google_identity_token", verified)
    monkeypatch.setattr(p, "register_native_google_account", signup)
    monkeypatch.setattr(p, "find_login_account", no_legacy_lookup)
    monkeypatch.setattr(p, "create_browser_session", session)
    with TestClient(app, base_url=ISSUER) as c:
        challenge = c.post("/identity/v1/provider/google/start",
                           headers={"Origin": ISSUER})
        assert challenge.status_code == 200
        assert challenge.json()["client_id"] == "verified-client"
        result = c.post("/identity/v1/provider/google/signup",
                        json={"state": "s" * 48, "credential": "id-token"},
                        headers={"Origin": ISSUER})
        assert result.status_code == 200
        assert result.json()["authenticated"] is True
        assert "__Host-dz_identity" in result.headers["set-cookie"]
