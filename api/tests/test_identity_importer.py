"""Offline tests for staging snapshot import; no real user data or database."""
import sys
from datetime import datetime, timezone
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from identity.importer import prepare_snapshot, import_into_staging
from identity.reconciliation import IdentityMigrationConflict


def users():
    return [
        {"id": "u1", "email": "a@example.test", "display_name": "A",
         "password_hash": "$argon2id$v=19$m=19456,t=2,p=1$dummy", "active": True,
         "email_verified_at": datetime.now(timezone.utc)},
        {"id": "u2", "email": "b@example.test", "display_name": "B",
         "password_hash": None, "active": False, "email_verified_at": None},
    ]


def test_bundle_preserves_existing_operly_ids_and_pending_only():
    bundle = prepare_snapshot(
        users(),
        [{"user_id": "u1", "provider": "google", "provider_subject": "google123"}],
        [{"user_id": "u2", "provider": "discord", "provider_subject": "discord123",
          "verified_at": datetime.now(timezone.utc)}],
    )
    assert bundle.counts() == {"accounts": 2, "provider_links": 2}
    assert [a.subject for a in bundle.accounts] == ["u1", "u2"]
    assert {x.provider: x.login_eligible for x in bundle.links} == {
        "google": True, "discord": False,
    }


@pytest.mark.parametrize("change", [
    lambda rows: rows[1].update(email="a@example.test"),
    lambda rows: rows[0].update(password_hash="unsupported"),
    lambda rows: rows[0].update(active=None),
    lambda rows: rows[0].update(email="A@example.test"),
])
def test_snapshot_conflicts_are_blocked(change):
    records = users()
    change(records)
    with pytest.raises(IdentityMigrationConflict):
        prepare_snapshot(records, [], [])


@pytest.mark.asyncio
async def test_import_refuses_without_explicit_approval(monkeypatch):
    bundle = prepare_snapshot(users(), [], [])
    monkeypatch.delenv("DRAGONZPYDER_IDENTITY_STAGING_IMPORT", raising=False)
    with pytest.raises(PermissionError):
        await import_into_staging(None, bundle, approved=True)
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_STAGING_IMPORT", "1")
    with pytest.raises(PermissionError):
        await import_into_staging(None, bundle, approved=False)


class FakeConnection:
    def __init__(self):
        self.rows = {"identity_accounts": 0, "identity_provider_links": 0}
        self.statements = []
    def transaction(self):
        class Tx:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *exc):
                return False
        return Tx()
    async def execute(self, query, *args):
        self.statements.append((query, args))
        if query.startswith("INSERT INTO identity_accounts"):
            self.rows["identity_accounts"] += 1
        if query.startswith("INSERT INTO identity_provider_links"):
            self.rows["identity_provider_links"] += 1
    async def fetchval(self, query):
        for table in self.rows:
            if table in query:
                return self.rows[table]
        raise AssertionError(query)


@pytest.mark.asyncio
async def test_atomic_import_writes_only_pending_accounts(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_STAGING_IMPORT", "1")
    conn = FakeConnection()
    bundle = prepare_snapshot(users(), [], [])
    result = await import_into_staging(conn, bundle, approved=True)
    assert result == {"accounts": 2, "provider_links": 0}
    assert any("pg_advisory_xact_lock" in q for q, _ in conn.statements)
    assert sum("INSERT INTO identity_accounts" in q for q, _ in conn.statements) == 2
    assert all("active')" not in q for q, _ in conn.statements if q.startswith("INSERT"))
    with pytest.raises(IdentityMigrationConflict):
        await import_into_staging(conn, bundle, approved=True)
