"""Synthetic-only offline transfer acceptance tests."""
import hashlib
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet, InvalidToken

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from identity.importer import prepare_snapshot
from identity.offline_transfer import seal, open_package, _write_private, _read_private, TTL_SECONDS
from identity.production_import import ApprovedInventory, read_source_snapshot
from identity.reconciliation import IdentityMigrationConflict


def sample():
    uid = str(uuid4())
    users = [{"id": uid, "email": "synthetic@example.test",
              "password_hash": None, "display_name": "Synthetic",
              "email_verified_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
              "active": True}]
    links = [{"user_id": uid, "provider": "google", "provider_subject": "synthetic-subject"}]
    return users, links


def digest(token):
    return hashlib.sha256(token).hexdigest()


def test_encrypted_roundtrip_preserves_identity_and_link():
    users, links = sample()
    bundle = prepare_snapshot(users, links, [])
    key = Fernet.generate_key()
    inventory = ApprovedInventory(1, 1)
    token = seal(bundle, inventory, 1, key)
    assert b"synthetic@example.test" not in token
    assert b"synthetic-subject" not in token
    assert open_package(token, inventory, 1, key, digest(token)) == bundle
    with pytest.raises(IdentityMigrationConflict):
        open_package(token, inventory, 0, key, digest(token))
    with pytest.raises(IdentityMigrationConflict):
        open_package(token, ApprovedInventory(2, 1), 1, key, digest(token))
    with pytest.raises(InvalidToken):
        open_package(token, inventory, 1, Fernet.generate_key(), digest(token))


def test_digest_tampering_and_expiry():
    users, links = sample()
    bundle = prepare_snapshot(users, links, [])
    key = Fernet.generate_key()
    inventory = ApprovedInventory(1, 1)
    token = seal(bundle, inventory, 0, key)
    with pytest.raises(IdentityMigrationConflict):
        open_package(token, inventory, 0, key, "0" * 64)
    changed = bytearray(token)
    changed[30] = ord("B") if changed[30] == ord("A") else ord("A")
    changed = bytes(changed)
    with pytest.raises(InvalidToken):
        open_package(changed, inventory, 0, key, digest(changed))
    f = Fernet(key)
    expired = f.encrypt_at_time(f.decrypt(token), int(time.time()) - TTL_SECONDS - 5)
    with pytest.raises(InvalidToken):
        open_package(expired, inventory, 0, key, digest(expired))


def test_private_file_exclusive_and_symlink_safe(tmp_path):
    path = tmp_path / "snapshot.enc"
    _write_private(path, b"ciphertext")
    assert path.stat().st_mode & 0o777 == 0o600
    assert _read_private(path) == b"ciphertext"
    with pytest.raises(FileExistsError):
        _write_private(path, b"replacement")
    symlink = tmp_path / "link"
    symlink.symlink_to(path)
    with pytest.raises(OSError):
        _read_private(symlink)
    os.chmod(path, 0o644)
    with pytest.raises(IdentityMigrationConflict):
        _read_private(path)


@pytest.mark.asyncio
async def test_unsupported_hash_requires_exact_recovery_inventory():
    users, links = sample()
    users[0]["password_hash"] = "$legacy$synthetic-only"

    class Source:
        def transaction(self, **kwargs):
            assert kwargs == {"isolation": "repeatable_read", "readonly": True}
            class Tx:
                async def __aenter__(self): return self
                async def __aexit__(self, *args): return False
            return Tx()
        async def fetchval(self, query): return True
        async def fetch(self, query):
            return users if "FROM public.app_users" in query else links

    inventory = ApprovedInventory(1, 1)
    with pytest.raises(IdentityMigrationConflict):
        await read_source_snapshot(Source(), inventory)
    bundle = await read_source_snapshot(Source(), inventory, expected_unsupported_passwords=1)
    assert bundle.accounts[0].password_hash is None
    assert users[0]["password_hash"] == "$legacy$synthetic-only"
    users[0]["password_hash"] = None
    with pytest.raises(IdentityMigrationConflict):
        await read_source_snapshot(Source(), inventory, expected_unsupported_passwords=1)


@pytest.mark.asyncio
async def test_cli_rejects_unapproved_import_before_file_or_network(monkeypatch, tmp_path):
    from argparse import Namespace
    from identity.offline_transfer import run
    args = Namespace(mode="import", expected_accounts=1, expected_google_links=1,
                     expected_unsupported_passwords=0, approve_pending_import=True,
                     package=str(tmp_path / "missing"), expected_sha256="0" * 64)
    monkeypatch.delenv("DRAGONZPYDER_IDENTITY_PRODUCTION_IMPORT", raising=False)
    with pytest.raises(PermissionError):
        await run(args, Fernet.generate_key())


@pytest.mark.asyncio
async def test_encrypted_package_to_pending_disposable_postgres(monkeypatch):
    import asyncpg
    from urllib.parse import urlsplit
    from identity.production_import import import_pending_production

    dsn = os.getenv("DRAGONZPYDER_IDENTITY_TEST_DSN", "")
    if not dsn:
        pytest.skip("No disposable identity_test PostgreSQL")
    if urlsplit(dsn).path != "/identity_test":
        raise RuntimeError("Never run against non-disposable database")
    users, links = sample()
    approved = ApprovedInventory(1, 1)
    key = Fernet.generate_key()
    token = seal(prepare_snapshot(users, links, []), approved, 0, key)
    bundle = open_package(token, approved, 0, key, digest(token))
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_PRODUCTION_IMPORT", "1")
    conn = await asyncpg.connect(dsn)
    tx = conn.transaction()
    await tx.start()
    try:
        assert not await conn.fetchval("SELECT to_regclass('public.identity_accounts') IS NOT NULL")
        sql = (Path(__file__).resolve().parents[1] / "identity" / "schema_bootstrap_manual.sql").read_text("utf-8")
        await conn.execute(sql.replace("BEGIN;\nSET LOCAL", "SET LOCAL", 1).removesuffix("COMMIT;\n"))
        result = await import_pending_production(conn, bundle, approved, operator_approved=True)
        assert result == {"accounts": 1, "provider_links": 1, "active_accounts": 0}
        assert await conn.fetchval("SELECT subject FROM public.identity_accounts") == users[0]["id"]
        with pytest.raises(IdentityMigrationConflict):
            await import_pending_production(conn, bundle, approved, operator_approved=True)
    finally:
        await tx.rollback()
        await conn.close()


def _manual_sql(name):
    sql = (Path(__file__).resolve().parents[1] / "identity" / name).read_text("utf-8")
    return sql.replace("BEGIN;\nSET LOCAL", "SET LOCAL", 1).removesuffix("COMMIT;\n")


@pytest.mark.asyncio
async def test_offline_roles_on_disposable_postgres(monkeypatch):
    import asyncpg
    from urllib.parse import urlsplit
    from identity.offline_transfer import _require_migration_role
    from identity.production_import import import_pending_production

    dsn = os.getenv("DRAGONZPYDER_IDENTITY_TEST_DSN", "")
    if not dsn:
        pytest.skip("No disposable identity_test PostgreSQL")
    if urlsplit(dsn).path != "/identity_test":
        raise RuntimeError("Never run against non-disposable database")
    conn = await asyncpg.connect(dsn)
    users, links = sample()
    inventory = ApprovedInventory(1, 1)
    uid = users[0]["id"]
    tx = conn.transaction()
    await tx.start()
    try:
        await conn.execute("""
            CREATE TABLE public.app_users (
                id uuid PRIMARY KEY, email text, password_hash text, display_name text,
                email_verified_at timestamptz, active boolean, unrelated_secret text
            );
            CREATE TABLE public.auth_identities (
                user_id uuid, provider text, provider_subject text
            );
            CREATE TABLE public.unrelated_data (value text);
        """)
        await conn.execute("""
            INSERT INTO public.app_users VALUES ($1::text::uuid,'synthetic@example.test',NULL,
                'Synthetic',$2,TRUE,'must-not-export')
        """, uid, users[0]["email_verified_at"])
        await conn.execute("INSERT INTO public.auth_identities VALUES ($1::text::uuid,'google','synthetic-subject')", uid)
        await conn.execute(_manual_sql("schema_export_role_manual.sql"))
        await conn.execute("SET SESSION AUTHORIZATION dz_identity_export")
        await _require_migration_role(conn, "dz_identity_export")
        # read_source_snapshot starts its own repeatable-read read-only transaction;
        # here the enclosing transaction is for DDL rollback, so test the exact
        # column grants directly, and use separate synthetic source tests for that reader.
        assert await conn.fetchval("SELECT id::text FROM public.app_users") == uid
        inventory_sql = (Path(__file__).resolve().parents[1] / "identity" / "source_inventory_manual.sql").read_text("utf-8")
        query = inventory_sql[inventory_sql.index("WITH users AS"):].split(";\nROLLBACK;", 1)[0]
        summary = await conn.fetchrow(query)
        assert summary["accounts"] == 1 and summary["google_links"] == 1
        assert summary["accounts_without_candidate_login"] == 0
        assert summary["invalid_uuid"] == 0
        for sql in ("SELECT unrelated_secret FROM public.app_users",
                    "SELECT value FROM public.unrelated_data",
                    "UPDATE public.app_users SET active=FALSE"):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                async with conn.transaction():
                    await conn.execute(sql)
        await conn.execute("RESET SESSION AUTHORIZATION")
    finally:
        await conn.execute("RESET SESSION AUTHORIZATION")
        await tx.rollback()

    tx = conn.transaction()
    await tx.start()
    try:
        await conn.execute(_manual_sql("schema_bootstrap_manual.sql"))
        await conn.execute(_manual_sql("schema_role_manual.sql"))
        await conn.execute(_manual_sql("schema_migration_role_manual.sql"))
        with pytest.raises(PermissionError):
            await _require_migration_role(conn, "dz_identity_migration")
        await conn.execute("SET SESSION AUTHORIZATION dz_identity_migration")
        await _require_migration_role(conn, "dz_identity_migration")
        monkeypatch.setenv("DRAGONZPYDER_IDENTITY_PRODUCTION_IMPORT", "1")
        bundle = prepare_snapshot(users, links, [])
        result = await import_pending_production(conn, bundle, inventory, operator_approved=True)
        assert result == {"accounts": 1, "provider_links": 1, "active_accounts": 0}
        for sql in ("SELECT password_hash FROM public.identity_accounts",
                    "UPDATE public.identity_accounts SET status='active'",
                    "DELETE FROM public.identity_accounts",
                    "UPDATE public.identity_oauth_clients SET enabled=TRUE"):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                async with conn.transaction():
                    await conn.execute(sql)
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            async with conn.transaction():
                await conn.execute("""
                    INSERT INTO public.identity_accounts
                        (subject,source_operly_user_id,identity_origin,email,display_name,source_active,status)
                    VALUES ('bad',NULL,'native_google','bad@example.test','Bad',TRUE,'active')
                """)
        await conn.execute("RESET SESSION AUTHORIZATION")
        assert await conn.fetchval("SELECT subject FROM public.identity_accounts") == uid
    finally:
        await conn.execute("RESET SESSION AUTHORIZATION")
        await tx.rollback()
        await conn.close()
