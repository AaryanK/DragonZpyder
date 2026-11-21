"""Synthetic password login, account-state, and browser cookie tests."""
import sys
from pathlib import Path
from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from identity.passwords import hash_password

SAMPLE_PASSPHRASE = "An Example Password 2026!"
from identity.password_login import password_login, LoginDenied
import identity.login_http as route
from identity.sessions import BrowserSession
from datetime import datetime, timedelta, timezone


class FakeDB:
    def __init__(self, stored):
        self.stored = stored
        self.count = 0
        self.email = "person@example.test"
        self.active = True
        self.queries = []
    async def fetchval(self, query, *args):
        if "identity_login_rate_limits" in query:
            self.count += 1
            return self.count
        raise AssertionError(query)
    async def fetchrow(self, query, *args):
        if "identity_accounts" in query:
            return {"subject": "person-1", "password_hash": self.stored} if self.active and args[0] == self.email else None
        raise AssertionError(query)
    async def execute(self, query, *args):
        self.queries.append((query,args))
        return "UPDATE 1"


@pytest.mark.asyncio
async def test_correct_password_uses_existing_identity_and_bad_password_fails(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_GRANT_HASH_KEY", "g" * 48)
    import identity.password_login as login
    db = FakeDB(hash_password("An Example Password 2026!"))
    async def make_session(conn, *, authenticated_subject):
        assert authenticated_subject == "person-1"
        return BrowserSession(secret="session-secret", csrf="csrf-secret",
                              expires_at=datetime.now(timezone.utc) + timedelta(days=7))
    monkeypatch.setattr(login, "create_browser_session", make_session)
    assert (await password_login(db, email="PERSON@EXAMPLE.TEST",
                                 password=SAMPLE_PASSPHRASE)).secret == "session-secret"
    with pytest.raises(LoginDenied):
        await password_login(db, email=db.email, password="incorrect")
    assert db.count == 2


@pytest.mark.asyncio
async def test_disabled_user_and_brute_force_limit(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_GRANT_HASH_KEY", "g" * 48)
    db = FakeDB(hash_password("An Example Password 2026!"))
    db.active = False
    with pytest.raises(LoginDenied):
        await password_login(db, email=db.email, password=SAMPLE_PASSPHRASE)
    db.active = True
    db.count = 8
    with pytest.raises(LoginDenied):
        await password_login(db, email=db.email, password=SAMPLE_PASSPHRASE)


def test_routes_hidden_by_default():
    app = FastAPI()
    app.include_router(route.router)
    with TestClient(app) as client:
        assert client.post("/identity/v1/password/login",
                           json={"email": "person@example.test", "password": "test"}).status_code == 404
        assert client.post("/identity/v1/logout").status_code == 404


def test_login_sets_host_only_cookies(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_HTTP_ENABLED", "1")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "staging")
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_ISSUER", "https://api.dragonzpyder.xyz")
    @asynccontextmanager
    async def fake_db():
        yield object()
    async def fake_login(conn, *, email, password):
        assert email == "person@example.test"
        return BrowserSession(secret="session-secret", csrf="csrf-secret",
                              expires_at=datetime.now(timezone.utc) + timedelta(days=7))
    monkeypatch.setattr(route, "_identity_db", fake_db)
    monkeypatch.setattr(route, "password_login", fake_login)
    app = FastAPI()
    app.include_router(route.router)
    with TestClient(app) as client:
        response = client.post("/identity/v1/password/login",
                               json={"email": "person@example.test", "password": "synthetic"},
                               headers={"Origin": "https://api.dragonzpyder.xyz"})
    assert response.status_code == 200
    cookies = response.headers.get_list("set-cookie")
    assert len(cookies) == 2
    assert all("secure" in x.lower() and "path=/" in x.lower() and "domain=" not in x.lower() for x in cookies)
    assert "httponly" in cookies[0].lower()
    assert "httponly" not in cookies[1].lower()
