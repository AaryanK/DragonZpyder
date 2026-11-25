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
