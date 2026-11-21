"""Synthetic browser session isolation, CSRF and revocation tests."""
import sys
from datetime import datetime, timezone
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from identity.sessions import create_browser_session, resolve_browser_session, revoke_browser_session, SessionDenied


class FakeDB:
    def __init__(self):
        self.active = {"account-1"}
        self.sessions = {}
    def transaction(self):
        class Tx:
            async def __aenter__(self): return self
            async def __aexit__(self, *ex): return False
        return Tx()
    async def fetchval(self, sql, *args):
        return 1 if args[0] in self.active else None
    async def execute(self, sql, *args):
        if sql.strip().startswith("INSERT"):
            digest, csrf_hash, sub, exp = args
            self.sessions[digest] = {
                "subject": sub, "csrf_hash": csrf_hash,
                "expires_at": exp, "revoked_at": None,
            }
        else:
            digest = args[0]
            if digest in self.sessions:
                self.sessions[digest]["revoked_at"] = datetime.now(timezone.utc)
    async def fetchrow(self, sql, *args):
        row = self.sessions.get(args[0])
        return row if row and row["subject"] in self.active else None


@pytest.mark.asyncio
async def test_cookie_session_rechecks_account_csrf_and_revocation(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_GRANT_HASH_KEY", "g" * 48)
    db = FakeDB()
    session = await create_browser_session(db, authenticated_subject="account-1")
    assert await resolve_browser_session(db, secret=session.secret) == "account-1"
    with pytest.raises(SessionDenied):
        await resolve_browser_session(db, secret=session.secret, require_csrf=True)
    with pytest.raises(SessionDenied):
        await resolve_browser_session(db, secret=session.secret, csrf="not-real", require_csrf=True)
    assert await resolve_browser_session(db, secret=session.secret, csrf=session.csrf,
                                         require_csrf=True) == "account-1"
    await revoke_browser_session(db, secret=session.secret)
    with pytest.raises(SessionDenied):
        await resolve_browser_session(db, secret=session.secret)


@pytest.mark.asyncio
async def test_disabled_account_cannot_create_or_use_session(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_GRANT_HASH_KEY", "g" * 48)
    db = FakeDB()
    session = await create_browser_session(db, authenticated_subject="account-1")
    db.active.clear()
    with pytest.raises(SessionDenied):
        await resolve_browser_session(db, secret=session.secret)
    with pytest.raises(SessionDenied):
        await create_browser_session(db, authenticated_subject="account-1")
