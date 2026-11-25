"""Private operator-only pending identity reconciliation; no activation or writes."""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import timezone

from .importer import prepare_snapshot
from .production_import import ApprovedInventory, _check_inventory
from .reconciliation import IdentityMigrationConflict


def snapshot_receipt(bundle, approved: ApprovedInventory, key: bytes) -> str:
    """Compare complete imported fields, not counts alone. Keep key off logs.

    Use an independently generated high-entropy 32-byte key shared privately
    between the two operator-side runs. Never publish per-account digests.
    """
    if not isinstance(key, bytes) or len(key) != 32:
        raise ValueError("A 32-byte reconciliation key is required")
    _check_inventory(bundle, approved)
    accounts = []
    for a in sorted(bundle.accounts, key=lambda x: x.subject):
        verified = a.email_verified_at
        if verified is not None:
            if verified.utcoffset() is None:
                raise IdentityMigrationConflict("Verification timestamp must be timezone-aware")
            verified = verified.astimezone(timezone.utc).isoformat()
        accounts.append([a.subject, a.email, a.password_hash, a.display_name,
                         verified, a.source_active])
    links = [[l.operly_user_id, l.provider, l.provider_subject, l.source, l.login_eligible]
             for l in sorted(bundle.links, key=lambda x: (x.operly_user_id, x.provider, x.provider_subject))]
    canonical = json.dumps(["dz-pending-reconciliation-v1", accounts, links],
                           ensure_ascii=True, separators=(",", ":")).encode()
    return hmac.new(key, canonical, hashlib.sha256).hexdigest()


async def read_pending_target(connection, approved: ApprovedInventory):
    """Read the still-fenced destination via a trusted operator connection.

    Never grant the temporary import role hash read privileges for this.
    Do not expose returned records to a model or API. Run separately from
    source snapshot reading in its own private network.
    """
    async with connection.transaction(isolation="repeatable_read", readonly=True):
        if await connection.fetchval("""
            SELECT current_setting('transaction_read_only')='on'
              AND to_regclass('public.app_users') IS NULL
              AND to_regclass('public.identity_accounts') IS NOT NULL
              AND EXISTS (SELECT 1 FROM pg_constraint
                   WHERE conname='identity_import_not_automatically_active'
                     AND conrelid=to_regclass('public.identity_accounts') AND convalidated)
              AND NOT EXISTS (SELECT 1 FROM public.identity_oauth_clients WHERE enabled)
              AND NOT EXISTS (SELECT 1 FROM public.identity_accounts
                   WHERE status<>'pending' OR identity_origin<>'operly_import'
                     OR source_operly_user_id IS DISTINCT FROM subject)
              AND NOT EXISTS (SELECT 1 FROM public.identity_provider_links
                   WHERE provider<>'google' OR source<>'auth' OR NOT login_eligible)
        """) is not True:
            raise IdentityMigrationConflict("Destination is no longer a fenced pending import")
        users = await connection.fetch("""
            SELECT subject AS id,email,password_hash,display_name,email_verified_at,
                   source_active AS active
            FROM public.identity_accounts ORDER BY subject
        """)
        links = await connection.fetch("""
            SELECT subject AS user_id,provider,provider_subject
            FROM public.identity_provider_links ORDER BY subject,provider,provider_subject
        """)
        bundle = prepare_snapshot([dict(u) for u in users], [dict(l) for l in links], [])
        _check_inventory(bundle, approved)
        return bundle


def compare_receipts(source: str, destination: str) -> None:
    if not all(isinstance(x, str) and len(x) == 64
               and all(c in "0123456789abcdef" for c in x) for x in (source, destination)):
        raise IdentityMigrationConflict("Invalid reconciliation receipt")
    if not hmac.compare_digest(source, destination):
        raise IdentityMigrationConflict("Imported identity fields differ; cutover must remain blocked")


async def generate_receipt(mode: str, approved: ApprovedInventory, key: bytes) -> str:
    """Use the existing scoped roles; never require administrator credentials."""
    import os
    import asyncpg
    from .offline_transfer import _require_migration_role
    from .production_import import read_source_snapshot
    from .http_bridge import _restricted_identity_role

    if mode == "source":
        dsn = os.environ["OPERLY_IDENTITY_EXPORT_DSN"]
    elif mode == "target":
        dsn = os.environ["DRAGONZPYDER_IDENTITY_DATABASE_URL"]
    else:
        raise ValueError("Unknown reconciliation mode")
    conn = await asyncpg.connect(dsn=dsn, timeout=10, command_timeout=30)
    try:
        if mode == "source":
            await _require_migration_role(conn, "dz_identity_export")
            bundle = await read_source_snapshot(conn, approved, expected_unsupported_passwords=0)
        else:
            await _restricted_identity_role(conn)
            bundle = await read_pending_target(conn, approved)
        return snapshot_receipt(bundle, approved, key)
    finally:
        await conn.close()


def main():
    """Operator CLI: aggregate receipts only, never print individual records."""
    import argparse
    import asyncio
    import getpass
    import re
    import warnings

    parser = argparse.ArgumentParser(description="Read-only pending identity reconciliation")
    sub = parser.add_subparsers(dest="mode", required=True)
    for mode in ("source", "target"):
        p = sub.add_parser(mode)
        p.add_argument("--expected-accounts", type=int, required=True)
        p.add_argument("--expected-google-links", type=int, required=True)
        p.add_argument("--approve-read-only", action="store_true", required=True)
    p = sub.add_parser("compare")
    p.add_argument("source_receipt")
    p.add_argument("target_receipt")
    args = parser.parse_args()
    try:
        if args.mode == "compare":
            compare_receipts(args.source_receipt, args.target_receipt)
            print("IDENTITY_RECONCILIATION_MATCH")
            return
        approved = ApprovedInventory(args.expected_accounts, args.expected_google_links)
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            key_text = getpass.getpass("Independent reconciliation key (64 hex characters): ")
        if not re.fullmatch(r"[0-9a-fA-F]{64}", key_text):
            raise ValueError("Invalid key format")
        receipt = asyncio.run(generate_receipt(args.mode, approved, bytes.fromhex(key_text)))
        print("IDENTITY_RECONCILIATION_RECEIPT:", receipt)
        print("IDENTITY_RECONCILIATION_READ_COMPLETE")
    except Exception:
        # Database errors, connection details and row values are never printed.
        print("IDENTITY_RECONCILIATION_FAILED")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
