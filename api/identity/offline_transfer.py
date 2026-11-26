"""Operator-only encrypted transfer between isolated production DB networks."""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
import getpass
import hashlib
import hmac
import json
import os
import re
import stat
import warnings

import asyncpg
from cryptography.fernet import Fernet

from .importer import prepare_snapshot
from .production_import import ApprovedInventory, _check_inventory, read_source_snapshot, import_pending_production
from .reconciliation import IdentityMigrationConflict

FORMAT = "dragonzpyder-pending-identities-v1"
MAX_BYTES = 16 * 1024 * 1024
TTL_SECONDS = 24 * 60 * 60


def _validate_recovery(approved, recovery):
    if type(recovery) is not int or not 0 <= recovery <= approved.accounts:
        raise IdentityMigrationConflict("Invalid recovery inventory")


def seal(bundle, approved, recovery, key):
    _validate_recovery(approved, recovery)
    _check_inventory(bundle, approved)
    if recovery > sum(a.password_hash is None for a in bundle.accounts):
        raise IdentityMigrationConflict("Recovery inventory inconsistent")
    payload = {
        "format": FORMAT, "recovery": recovery,
        "accounts": [
            {"id": a.subject, "email": a.email, "password_hash": a.password_hash,
             "display_name": a.display_name, "active": a.source_active,
             "email_verified_at": a.email_verified_at.isoformat() if a.email_verified_at else None}
            for a in bundle.accounts
        ],
        "google_links": [
            {"user_id": l.operly_user_id, "provider": l.provider,
             "provider_subject": l.provider_subject} for l in bundle.links
        ],
    }
    token = Fernet(key).encrypt(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    if len(token) > MAX_BYTES:
        raise IdentityMigrationConflict("Package exceeds size limit")
    return token


def open_package(token, approved, recovery, key, expected_sha256):
    _validate_recovery(approved, recovery)
    if not 0 < len(token) <= MAX_BYTES:
        raise IdentityMigrationConflict("Invalid package size")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise IdentityMigrationConflict("Invalid package digest")
    if not hmac.compare_digest(hashlib.sha256(token).hexdigest(), expected_sha256):
        raise IdentityMigrationConflict("Package digest mismatch")
    data = json.loads(Fernet(key).decrypt(token, ttl=TTL_SECONDS))
    if (not isinstance(data, dict)
        or set(data) != {"format", "recovery", "accounts", "google_links"}
        or data["format"] != FORMAT or type(data["recovery"]) is not int
        or data["recovery"] != recovery
        or not isinstance(data["accounts"], list)
        or not isinstance(data["google_links"], list)
        or len(data["accounts"]) != approved.accounts
        or len(data["google_links"]) != approved.google_links):
        raise IdentityMigrationConflict("Package inventory mismatch")
    for row in data["accounts"]:
        if set(row) != {"id", "email", "password_hash", "display_name", "active", "email_verified_at"}:
            raise IdentityMigrationConflict("Invalid account record")
        if row["email_verified_at"] is not None:
            row["email_verified_at"] = datetime.fromisoformat(row["email_verified_at"])
            if row["email_verified_at"].utcoffset() is None:
                raise IdentityMigrationConflict("Timestamp must be timezone-aware")
    for row in data["google_links"]:
        if set(row) != {"user_id", "provider", "provider_subject"}:
            raise IdentityMigrationConflict("Invalid provider record")
    bundle = prepare_snapshot(data["accounts"], data["google_links"], [])
    _check_inventory(bundle, approved)
    if recovery > sum(a.password_hash is None for a in bundle.accounts):
        raise IdentityMigrationConflict("Recovery inventory inconsistent")
    return bundle


def _write_private(path, token):
    # Exclusive creation: never overwrite an existing file or follow a symlink.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(token)
            out.flush()
            os.fsync(out.fileno())
    except BaseException:
        # Do not leave a partial package with a misleading successful name.
        os.unlink(path)
        raise


def _read_private(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as src:
        info = os.fstat(src.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077
            or info.st_uid != os.geteuid() or not 0 < info.st_size <= MAX_BYTES):
            raise IdentityMigrationConflict("Package must be a private regular file")
        token = src.read(MAX_BYTES + 1)
    if len(token) != info.st_size:
        raise IdentityMigrationConflict("Package size changed")
    return token


def _key():
    # Refuse getpass's insecure fallback. No key in args, environment or logs.
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        return getpass.getpass("Transfer key (hidden): ").encode("ascii")


async def _require_migration_role(conn, role):
    # Fail closed on accidental use of an administrative or application DSN.
    allowed = await conn.fetchval("""
        SELECT current_user=$1 AND session_user=current_user
          AND NOT (r.rolsuper OR r.rolcreaterole OR r.rolcreatedb OR
                   r.rolreplication OR r.rolbypassrls OR r.rolinherit)
          AND NOT EXISTS (SELECT 1 FROM pg_auth_members m WHERE m.member=r.oid)
          AND NOT EXISTS (SELECT 1 FROM pg_database d WHERE d.datname=current_database()
                          AND d.datdba=r.oid)
          AND NOT has_database_privilege(current_user,current_database(),'CREATE')
          AND NOT has_schema_privilege(current_user,'public','CREATE')
          AND NOT EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                          WHERE n.nspname='public' AND c.relowner=r.oid)
        FROM pg_roles r WHERE r.rolname=current_user
    """, role)
    if allowed is not True:
        raise PermissionError("Dedicated migration role required")
    if role == "dz_identity_export":
        allowed = await conn.fetchval("""
            SELECT NOT EXISTS (
                SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','f')
                  AND (has_any_column_privilege(current_user,c.oid,'INSERT,UPDATE,REFERENCES')
                    OR has_table_privilege(current_user,c.oid,'DELETE,TRUNCATE,TRIGGER')
                    OR (c.relname NOT IN ('app_users','auth_identities')
                        AND has_any_column_privilege(current_user,c.oid,'SELECT'))))
        """)
    else:
        allowed = await conn.fetchval("""
            SELECT NOT EXISTS (
                SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','f')
                  AND (has_any_column_privilege(current_user,c.oid,'UPDATE,REFERENCES')
                    OR has_table_privilege(current_user,c.oid,'DELETE,TRUNCATE,TRIGGER')
                    OR (c.relname NOT IN ('identity_accounts','identity_provider_links')
                        AND has_any_column_privilege(current_user,c.oid,'INSERT'))))
              AND NOT has_column_privilege(current_user,'public.identity_accounts','password_hash','SELECT')
        """)
    if allowed is not True:
        raise PermissionError("Migration role has unexpected effective permissions")


async def run(args, key):
    approved = ApprovedInventory(args.expected_accounts, args.expected_google_links)
    recovery = args.expected_unsupported_passwords
    _validate_recovery(approved, recovery)
    if args.mode == "export":
        if not args.approve_export:
            raise PermissionError("Explicit export approval required")
        source = await asyncpg.connect(os.environ["OPERLY_IDENTITY_EXPORT_DSN"], timeout=10, command_timeout=30)
        try:
            await _require_migration_role(source, 'dz_identity_export')
            bundle = await read_source_snapshot(source, approved, expected_unsupported_passwords=recovery)
        finally:
            await source.close()
        token = seal(bundle, approved, recovery, key)
        _write_private(args.package, token)
        return {**bundle.counts(), "unsupported_passwords_omitted": recovery,
                "package_sha256": hashlib.sha256(token).hexdigest()}
    if not args.approve_pending_import or os.getenv("DRAGONZPYDER_IDENTITY_PRODUCTION_IMPORT") != "1":
        raise PermissionError("Explicit pending-import approval required")
    bundle = open_package(_read_private(args.package), approved, recovery, key, args.expected_sha256)
    target = await asyncpg.connect(os.environ["DRAGONZPYDER_IDENTITY_MIGRATION_DSN"], timeout=10, command_timeout=30)
    try:
        await _require_migration_role(target, 'dz_identity_migration')
        result = await import_pending_production(target, bundle, approved, operator_approved=True)
    finally:
        await target.close()
    return {**result, "unsupported_passwords_omitted": recovery}


def main():
    parser = argparse.ArgumentParser(description="Encrypted pending identity transfer; no activation")
    sub = parser.add_subparsers(dest="mode", required=True)
    for mode in ("export", "import"):
        p = sub.add_parser(mode)
        p.add_argument("--package", required=True)
        p.add_argument("--expected-accounts", type=int, required=True)
        p.add_argument("--expected-google-links", type=int, required=True)
        p.add_argument("--expected-unsupported-passwords", type=int, required=True)
        if mode == "export":
            p.add_argument("--approve-export", action="store_true")
        else:
            p.add_argument("--expected-sha256", required=True)
            p.add_argument("--approve-pending-import", action="store_true")
    args = parser.parse_args()
    try:
        result = asyncio.run(run(args, _key()))
    except Exception:
        print("IDENTITY_OFFLINE_TRANSFER_FAILED")
        raise SystemExit(1) from None
    print(json.dumps(result, sort_keys=True))
    print("IDENTITY_OFFLINE_TRANSFER_COMPLETE")


if __name__ == "__main__":
    main()
