"""Operator-only pending identity import. Never mounted as HTTP or agent tool.

Use an authorized migration runner with independently scoped connections.
No raw rows, hashes, tokens, emails, or database URLs are logged.
Existing Operly authorization and all channel identities stay in Operly.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from uuid import UUID

import asyncpg

from .importer import ImportBundle, prepare_snapshot
from .reconciliation import IdentityMigrationConflict

@dataclass(frozen=True)
class ApprovedInventory:
    accounts: int
    google_links: int

    def __post_init__(self):
        if self.accounts < 1 or not 0 <= self.google_links <= self.accounts:
            raise IdentityMigrationConflict("Invalid approved inventory")

def _canonical_uuid(value):
    try:
        if str(UUID(value)) != value:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise IdentityMigrationConflict("Source identity is not a canonical UUID") from None
    return value

def _utc(value):
    if value is None:
        return None
    if not isinstance(value, datetime):
        raise IdentityMigrationConflict("Invalid verification timestamp")
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

def _check_inventory(bundle: ImportBundle, approved: ApprovedInventory):
    if bundle.counts() != {"accounts": approved.accounts, "provider_links": approved.google_links}:
        raise IdentityMigrationConflict("Source inventory changed; re-review counts before import")
    if any(link.provider != "google" or link.source != "auth" or not link.login_eligible
           for link in bundle.links):
        raise IdentityMigrationConflict("Only explicit Google login bindings may migrate")
    for account in bundle.accounts:
        _canonical_uuid(account.subject)

async def read_source_snapshot(connection, approved: ApprovedInventory, *,
                               expected_unsupported_passwords: int = 0) -> ImportBundle:
    # Explicit count approval is required before omitting incompatible hashes.
    # Affected accounts remain pending; activation requires separate recovery proof.
    if not 0 <= expected_unsupported_passwords <= approved.accounts:
        raise IdentityMigrationConflict("Invalid unsupported password inventory")
    # A read-only transaction forbids writes even if an operator supplied a
    # credential with more privileges. Use a read-only export role nonetheless.
    async with connection.transaction(isolation="repeatable_read", readonly=True):
        if not await connection.fetchval("""
            SELECT current_setting('transaction_read_only')='on'
            AND to_regclass('public.app_users') IS NOT NULL
            AND to_regclass('public.auth_identities') IS NOT NULL
            AND to_regclass('public.identity_accounts') IS NULL
        """):
            raise IdentityMigrationConflict("Unexpected source database")
        source_users = await connection.fetch("""
            SELECT id::text AS id,email,password_hash,display_name,email_verified_at,active
            FROM public.app_users ORDER BY id
        """)
        auth = await connection.fetch("""
            SELECT user_id::text AS user_id,provider,provider_subject
            FROM public.auth_identities WHERE provider='google'
            ORDER BY user_id,provider_subject
        """)
        users = []
        unsupported = 0
        for row in source_users:
            user = dict(row)
            _canonical_uuid(user["id"])
            user["email_verified_at"] = _utc(user["email_verified_at"])
            password_hash = user.get("password_hash")
            if password_hash is not None:
                if not isinstance(password_hash, str) or not 1 <= len(password_hash) <= 2048:
                    raise IdentityMigrationConflict("Malformed source password hash")
                if not password_hash.startswith(("$argon2id$", "pbkdf2_sha256$")):
                    unsupported += 1
                    user["password_hash"] = None
            users.append(user)
        if unsupported != expected_unsupported_passwords:
            raise IdentityMigrationConflict("Unsupported password inventory changed; review recovery before export")
        # External identities are channel bindings, not first-party login
        # credentials. Discord login links are also deliberately deferred.
        bundle = prepare_snapshot(users, [dict(r) for r in auth], [])
        _check_inventory(bundle, approved)
        return bundle

async def import_pending_production(connection, bundle: ImportBundle,
                                    approved: ApprovedInventory, *,
                                    operator_approved: bool = False):
    if not operator_approved or os.getenv("DRAGONZPYDER_IDENTITY_PRODUCTION_IMPORT") != "1":
        raise PermissionError("Explicit pending-import approval required")
    _check_inventory(bundle, approved)
    async with connection.transaction():
        await connection.execute("SELECT pg_advisory_xact_lock(739110211)")
        if not await connection.fetchval("""
            SELECT current_user <> 'dz_identity_api'
              AND to_regclass('public.app_users') IS NULL
              AND to_regclass('public.identity_accounts') IS NOT NULL
              AND EXISTS (SELECT 1 FROM pg_constraint
                          WHERE conname='identity_import_not_automatically_active'
                            AND conrelid='public.identity_accounts'::regclass
                            AND convalidated)
              AND NOT EXISTS (SELECT 1 FROM public.identity_oauth_clients WHERE enabled)
        """):
            raise IdentityMigrationConflict("Unexpected target or activation guard missing")
        for table in ("identity_accounts", "identity_provider_links",
                      "identity_browser_sessions", "identity_authorization_codes",
                      "identity_refresh_grants"):
            if await connection.fetchval("SELECT count(*) FROM public." + table) != 0:
                raise IdentityMigrationConflict("Target must be unused and empty")
        for account in bundle.accounts:
            await connection.execute("""
                INSERT INTO public.identity_accounts
                    (subject,source_operly_user_id,identity_origin,email,password_hash,
                     display_name,email_verified_at,source_active,status)
                VALUES ($1,$1,'operly_import',$2,$3,$4,$5,$6,'pending')
            """, account.subject, account.email, account.password_hash, account.display_name,
                account.email_verified_at, account.source_active)
        for link in bundle.links:
            await connection.execute("""
                INSERT INTO public.identity_provider_links
                    (subject,provider,provider_subject,source,login_eligible)
                VALUES ($1,'google',$2,'auth',TRUE)
            """, link.operly_user_id, link.provider_subject)
        counts = {
            "accounts": await connection.fetchval("SELECT count(*) FROM public.identity_accounts"),
            "provider_links": await connection.fetchval("SELECT count(*) FROM public.identity_provider_links"),
            "active_accounts": await connection.fetchval("SELECT count(*) FROM public.identity_accounts WHERE status='active'"),
        }
        if counts != {"accounts": approved.accounts, "provider_links": approved.google_links, "active_accounts": 0}:
            raise IdentityMigrationConflict("Target count reconciliation failed")
    return counts

async def _run(args):
    if os.getenv("DRAGONZPYDER_IDENTITY_PRODUCTION_IMPORT") != "1" or not args.approve_pending_import:
        raise PermissionError("Explicit pending-import approval required")
    source_dsn = os.environ["OPERLY_IDENTITY_EXPORT_DSN"]
    target_dsn = os.environ["DRAGONZPYDER_IDENTITY_MIGRATION_DSN"]
    if not source_dsn or not target_dsn or source_dsn == target_dsn:
        raise IdentityMigrationConflict("Distinct authorized source/target connections required")
    approved = ApprovedInventory(args.expected_accounts, args.expected_google_links)
    source = await asyncpg.connect(source_dsn, timeout=10, command_timeout=30)
    try:
        bundle = await read_source_snapshot(source, approved)
    finally:
        await source.close()
    target = await asyncpg.connect(target_dsn, timeout=10, command_timeout=30)
    try:
        return await import_pending_production(target, bundle, approved, operator_approved=True)
    finally:
        await target.close()

def main():
    parser = argparse.ArgumentParser(description="Authorized insert-only pending identity migration")
    parser.add_argument("--expected-accounts", type=int, required=True)
    parser.add_argument("--expected-google-links", type=int, required=True)
    parser.add_argument("--approve-pending-import", action="store_true")
    args = parser.parse_args()
    try:
        result = asyncio.run(_run(args))
    except Exception:
        # Do not print tracebacks, row data, connection strings, or DB errors.
        print("IDENTITY_PENDING_IMPORT_FAILED")
        raise SystemExit(1) from None
    print(json.dumps(result, sort_keys=True))
    print("IDENTITY_PENDING_IMPORT_COMPLETE")

if __name__ == "__main__":
    main()
