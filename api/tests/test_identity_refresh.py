"""Synthetic refresh-family replay and rotation tests with fake SQL connection."""
import sys
from pathlib import Path
from datetime import datetime, timezone

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from identity.refresh import issue_refresh, rotate_refresh, revoke_refresh_family
from identity.grants import OAuthGrantDenied


REDIRECT = "https://operly.dragonzpyder.xyz/auth/callback"


class FakeDB:
    def __init__(self):
        self.grants = {}
        self.enabled = True
    def transaction(self):
        class Tx:
            async def __aenter__(self): return self
            async def __aexit__(self, *exc): return False
        return Tx()
    async def fetchval(self, query, *args):
        if "FROM identity_accounts" in query:
            return 1 if self.enabled else None
        if "SELECT family_id" in query:
            row = self.grants.get(args[0])
            return row["family_id"] if row else None
        raise AssertionError(query)
    async def fetchrow(self, query, *args):
        if "FROM identity_oauth_clients" in query:
            return {"client_id": "operly-web", "redirect_uri": REDIRECT,
                    "allowed_scope": "operly:access", "audience": "operly-api"}
        if "FROM identity_refresh_grants" in query:
            return self.grants.get(args[0])
        raise AssertionError(query)
    async def execute(self, query, *args):
        if "pg_advisory_xact_lock" in query:
            return "SELECT 1"
        if "INSERT INTO identity_refresh_grants" in query:
            digest,subject,client,family,scope,audience,expiry = args
            self.grants[digest] = {
                "subject":subject, "client_id":client,"family_id":family,
                "scope":scope,"audience":audience,"expires_at":expiry,
                "consumed_at":None,"revoked_at":None,
            }
            return "INSERT 0 1"
        if "SET consumed_at=now()" in query:
            row = self.grants[args[0]]
            if row["consumed_at"] is not None or row["revoked_at"] is not None:
                return "UPDATE 0"
            row["consumed_at"] = datetime.now(timezone.utc)
            return "UPDATE 1"
        if "SET revoked_at=now()" in query:
            for row in self.grants.values():
                if row["family_id"] == args[0]:
                    row["revoked_at"] = datetime.now(timezone.utc)
            return "UPDATE 2"
        raise AssertionError(query)


@pytest.mark.asyncio
async def test_rotate_and_replay_revoke_entire_family(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_GRANT_HASH_KEY", "z" * 48)
    db = FakeDB()
    initial = await issue_refresh(db, subject="existing-id", client_id="operly-web",
                                  redirect_uri=REDIRECT, scope="operly:access")
    second = await rotate_refresh(db, token=initial.value, client_id="operly-web",
                                  redirect_uri=REDIRECT)
    assert second.subject == "existing-id"
    assert second.value != initial.value
    assert second.expires_at == initial.expires_at
    # Wrong-client replay is rejected without revoking the real family.
    with pytest.raises(OAuthGrantDenied):
        await rotate_refresh(db, token=initial.value, client_id="different-client",
                             redirect_uri=REDIRECT)
    assert all(row["revoked_at"] is None for row in db.grants.values())
    with pytest.raises(OAuthGrantDenied):
        await rotate_refresh(db, token=initial.value, client_id="operly-web",
                             redirect_uri=REDIRECT)
    assert all(row["revoked_at"] is not None for row in db.grants.values())
    with pytest.raises(OAuthGrantDenied):
        await rotate_refresh(db, token=second.value, client_id="operly-web",
                             redirect_uri=REDIRECT)


@pytest.mark.asyncio
async def test_revoke_and_inactive_account_fail_closed(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_GRANT_HASH_KEY", "z" * 48)
    db = FakeDB()
    initial = await issue_refresh(db, subject="existing-id", client_id="operly-web",
                                  redirect_uri=REDIRECT, scope="operly:access")
    db.enabled = False
    with pytest.raises(OAuthGrantDenied):
        await rotate_refresh(db, token=initial.value, client_id="operly-web",
                             redirect_uri=REDIRECT)
    db.enabled = True
    await revoke_refresh_family(db, token=initial.value)
    with pytest.raises(OAuthGrantDenied):
        await rotate_refresh(db, token=initial.value, client_id="operly-web",
                             redirect_uri=REDIRECT)
