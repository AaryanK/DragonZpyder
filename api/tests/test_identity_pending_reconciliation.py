"""Reconciliation regression tests with synthetic identities only."""
from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from identity.importer import prepare_snapshot
from identity.pending_reconciliation import snapshot_receipt, compare_receipts
from identity.production_import import ApprovedInventory
from identity.reconciliation import IdentityMigrationConflict


def sample():
    uid = str(uuid4())
    users = [{"id": uid, "email": "example@example.test", "display_name": "Example",
              "password_hash": None, "email_verified_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
              "active": True}]
    links = [{"user_id": uid, "provider": "google", "provider_subject": "synthetic-subject"}]
    return prepare_snapshot(users, links, [])


@pytest.mark.parametrize("field,value", [
    ("email", "other@example.test"), ("display_name", "Changed"),
    ("password_hash", "pbkdf2_sha256$synthetic"),
    ("source_active", False), ("email_verified_at", None),
])
def test_equal_count_field_changes_are_detected(field, value):
    bundle = sample()
    approved = ApprovedInventory(1, 1)
    key = b"x" * 32
    changed = replace(bundle, accounts=(replace(bundle.accounts[0], **{field: value}),))
    with pytest.raises(IdentityMigrationConflict):
        compare_receipts(snapshot_receipt(bundle, approved, key), snapshot_receipt(changed, approved, key))


def test_provider_subject_and_key_changes_detected():
    bundle = sample()
    approved = ApprovedInventory(1, 1)
    key = b"x" * 32
    changed = replace(bundle, links=(replace(bundle.links[0], provider_subject="changed"),))
    original = snapshot_receipt(bundle, approved, key)
    compare_receipts(original, snapshot_receipt(bundle, approved, key))
    for candidate in (snapshot_receipt(changed, approved, key),
                      snapshot_receipt(bundle, approved, b"y" * 32)):
        with pytest.raises(IdentityMigrationConflict):
            compare_receipts(original, candidate)
    with pytest.raises(ValueError):
        snapshot_receipt(bundle, approved, b"short")


def test_receipt_order_independent():
    a, b = sample(), sample()
    b = replace(b, accounts=(replace(b.accounts[0], email="second@example.test"),),
                links=(replace(b.links[0], provider_subject="second"),))
    combined = replace(a, accounts=a.accounts+b.accounts, links=a.links+b.links)
    reverse = replace(combined, accounts=combined.accounts[::-1], links=combined.links[::-1])
    approved = ApprovedInventory(2, 2)
    assert snapshot_receipt(combined, approved, b"x"*32) == snapshot_receipt(reverse, approved, b"x"*32)


@pytest.mark.asyncio
async def test_pending_receipt_real_postgres(monkeypatch):
    import os
    import asyncpg
    from urllib.parse import urlsplit
    from identity.pending_reconciliation import read_pending_target
    from identity.production_import import import_pending_production

    dsn = os.getenv("DRAGONZPYDER_IDENTITY_TEST_DSN", "")
    if not dsn:
        pytest.skip("No disposable identity_test PostgreSQL")
    if urlsplit(dsn).path != "/identity_test":
        raise RuntimeError("Never run against non-disposable database")
    bundle, approved, key = sample(), ApprovedInventory(1, 1), b"x"*32
    conn = await asyncpg.connect(dsn)
    try:
        assert not await conn.fetchval("SELECT to_regclass('public.identity_accounts') IS NOT NULL")
        sql = (Path(__file__).resolve().parents[1] / "identity" / "schema_bootstrap_manual.sql").read_text("utf-8")
        await conn.execute(sql)
        try:
            monkeypatch.setenv("DRAGONZPYDER_IDENTITY_PRODUCTION_IMPORT", "1")
            await import_pending_production(conn, bundle, approved, operator_approved=True)
            target = await read_pending_target(conn, approved)
            compare_receipts(snapshot_receipt(bundle, approved, key), snapshot_receipt(target, approved, key))
            await conn.execute("UPDATE public.identity_accounts SET display_name='Changed'")
            target = await read_pending_target(conn, approved)
            with pytest.raises(IdentityMigrationConflict):
                compare_receipts(snapshot_receipt(bundle, approved, key), snapshot_receipt(target, approved, key))
            await conn.execute("UPDATE public.identity_oauth_clients SET enabled=TRUE")
            with pytest.raises(IdentityMigrationConflict):
                await read_pending_target(conn, approved)
        finally:
            await conn.execute("""
                DROP TABLE public.identity_authorization_interactions,
                public.identity_provider_challenges, public.identity_login_rate_limits,
                public.identity_refresh_grants, public.identity_authorization_codes,
                public.identity_browser_sessions, public.identity_provider_links,
                public.identity_oauth_clients, public.identity_accounts
            """)
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode,env,role", [
    ("source", "OPERLY_IDENTITY_EXPORT_DSN", "dz_identity_export"),
    ("target", "DRAGONZPYDER_IDENTITY_DATABASE_URL", "dz_identity_api"),
])
async def test_receipt_cli_uses_scoped_connection(monkeypatch, mode, env, role):
    import asyncpg
    from identity import pending_reconciliation as module
    from identity import http_bridge, offline_transfer, production_import

    bundle, approved, key = sample(), ApprovedInventory(1, 1), b"x"*32
    events = []
    class Conn:
        async def close(self):
            events.append("close")
    conn = Conn()
    async def connect(**kwargs):
        assert kwargs["dsn"] == "test-only-dsn"
        return conn
    async def check_source(c, requested):
        assert c is conn and requested == role
        events.append("check")
    async def check_target(c):
        assert c is conn and role == "dz_identity_api"
        events.append("check")
    async def read_source(c, inventory, *, expected_unsupported_passwords):
        assert c is conn and inventory == approved and expected_unsupported_passwords == 0
        events.append("read")
        return bundle
    async def read_target(c, inventory):
        assert c is conn and inventory == approved
        events.append("read")
        return bundle
    monkeypatch.setenv(env, "test-only-dsn")
    monkeypatch.setattr(asyncpg, "connect", connect)
    monkeypatch.setattr(offline_transfer, "_require_migration_role", check_source)
    monkeypatch.setattr(http_bridge, "_restricted_identity_role", check_target)
    monkeypatch.setattr(production_import, "read_source_snapshot", read_source)
    monkeypatch.setattr(module, "read_pending_target", read_target)
    assert await module.generate_receipt(mode, approved, key) == snapshot_receipt(bundle, approved, key)
    assert events == ["check", "read", "close"]


def test_cli_compare_does_not_print_receipts(monkeypatch, capsys):
    from identity import pending_reconciliation as module
    monkeypatch.setattr(sys, "argv", ["receipt", "compare", "a"*64, "b"*64])
    with pytest.raises(SystemExit):
        module.main()
    assert capsys.readouterr().out.strip() == "IDENTITY_RECONCILIATION_FAILED"
    monkeypatch.setattr(sys, "argv", ["receipt", "compare", "a"*64, "a"*64])
    module.main()
    assert capsys.readouterr().out.strip() == "IDENTITY_RECONCILIATION_MATCH"
