"""Strict staging import of Operly accounts and verified provider links.

Never run from an API route or an agent tool. Snapshot records must be obtained
from an authorized, isolated export and transported by a trusted operator.
No logging of row data or password hashes. The DB transaction is all-or-nothing.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Mapping, Sequence

from .reconciliation import IdentityMigrationConflict, IdentityPlan, reconcile, _required_string


@dataclass(frozen=True)
class ImportAccount:
    subject: str
    email: str
    password_hash: str | None
    display_name: str
    email_verified_at: datetime | None
    source_active: bool


@dataclass(frozen=True)
class ImportBundle:
    accounts: tuple[ImportAccount, ...]
    links: tuple
    def counts(self) -> dict[str, int]:
        return {"accounts": len(self.accounts), "provider_links": len(self.links)}


def prepare_snapshot(users: Sequence[Mapping], auth_identities: Sequence[Mapping],
                     external_identities: Sequence[Mapping]) -> ImportBundle:
    """Prepare canonical IDs while rejecting source-account conflicts."""
    plan: IdentityPlan = reconcile(users, auth_identities, external_identities)
    accounts: list[ImportAccount] = []
    seen_email: set[str] = set()
    for user in users:
        subject = _required_string(user, "id", 120)
        email = _required_string(user, "email", 320)
        if email != email.lower() or "@" not in email:
            raise IdentityMigrationConflict("Source email requires manual normalization")
        if email in seen_email:
            raise IdentityMigrationConflict("Duplicate email requires reconciliation")
        seen_email.add(email)
        password_hash = user.get("password_hash")
        if password_hash is not None and (
            not isinstance(password_hash, str) or
            len(password_hash) > 2048 or
            not (password_hash.startswith("$argon2id$") or password_hash.startswith("pbkdf2_sha256$"))
        ):
            raise IdentityMigrationConflict("Unsupported source password hash")
        display_name = _required_string(user, "display_name", 200)
        verified_at = user.get("email_verified_at")
        if verified_at is not None and not isinstance(verified_at, datetime):
            raise IdentityMigrationConflict("Invalid verification timestamp")
        active = user.get("active")
        if type(active) is not bool:
            raise IdentityMigrationConflict("Source account active flag missing")
        accounts.append(ImportAccount(subject, email, password_hash, display_name, verified_at, active))
    if set(a.subject for a in accounts) != set(plan.user_ids):
        raise IdentityMigrationConflict("Account reconciliation mismatch")
    return ImportBundle(tuple(sorted(accounts, key=lambda a: a.subject)), plan.links)


async def import_into_staging(connection, bundle: ImportBundle, *, approved: bool = False) -> dict[str, int]:
    """Atomic insert-only import into an explicitly isolated staging database.

    Reject nonempty destination tables. The connection must be an asyncpg
    connection from a trusted migration-only process and a staging DB role.
    """
    if not approved or os.getenv("DRAGONZPYDER_IDENTITY_STAGING_IMPORT") != "1":
        raise PermissionError("Identity import requires explicit staging authorization")
    if not bundle.accounts:
        raise IdentityMigrationConflict("Empty import is forbidden")
    async with connection.transaction():
        await connection.execute("SELECT pg_advisory_xact_lock(739110211)")
        for table in ("identity_accounts", "identity_provider_links"):
            count = await connection.fetchval("SELECT count(*) FROM " + table)
            if count != 0:
                raise IdentityMigrationConflict("Destination is not an empty staging identity database")
        for a in bundle.accounts:
            await connection.execute(
                """INSERT INTO identity_accounts
                   (subject, source_operly_user_id, email, password_hash, display_name,
                    email_verified_at, source_active, status)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, 'pending')""",
                a.subject, a.subject, a.email, a.password_hash, a.display_name,
                a.email_verified_at, a.source_active,
            )
        for link in bundle.links:
            await connection.execute(
                """INSERT INTO identity_provider_links
                   (subject, provider, provider_subject, source, login_eligible)
                   VALUES ($1, $2, $3, $4, $5)""",
                link.operly_user_id, link.provider, link.provider_subject,
                link.source, link.login_eligible,
            )
        accounts = await connection.fetchval("SELECT count(*) FROM identity_accounts")
        links = await connection.fetchval("SELECT count(*) FROM identity_provider_links")
        if (accounts, links) != (len(bundle.accounts), len(bundle.links)):
            raise IdentityMigrationConflict("Staging import row count mismatch")
    return bundle.counts()
