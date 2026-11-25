"""Conservative planning for password recovery performed by the source owner.

A plan is not authorization to write. Never log plan contents, hashes, or IDs.
The source must be freshly reconciled under a controlled write freeze or a
reviewed per-account source-authority handoff before applying any change.
"""
from dataclasses import dataclass, field, replace

from .importer import ImportBundle
from .production_import import ApprovedInventory, _check_inventory
from .reconciliation import IdentityMigrationConflict


@dataclass(frozen=True)
class RecoveryAddition:
    subject: str = field(repr=False)
    new_hash: str = field(repr=False)


def plan_recovery_additions(source: ImportBundle, target: ImportBundle,
                            approved: ApprovedInventory) -> tuple[RecoveryAddition, ...]:
    """Only accept null-to-hash recovery for already verified pending users.

    This intentionally refuses password rotation, account creation/deletion,
    provider relinking, email changes, verification changes and deactivation.
    Those require a separate reviewed reconciliation. The target must be read
    by read_pending_target (which checks the original pending-only fence).
    """
    _check_inventory(source, approved)
    _check_inventory(target, approved)
    if set(source.links) != set(target.links):
        raise IdentityMigrationConflict("Provider bindings changed")
    current = {a.subject: a for a in target.accounts}
    if len(current) != approved.accounts or set(current) != {a.subject for a in source.accounts}:
        raise IdentityMigrationConflict("Identity subjects changed")
    additions = []
    for a in source.accounts:
        prior = current[a.subject]
        if replace(a, password_hash=prior.password_hash) != prior:
            raise IdentityMigrationConflict("Non-password identity fields changed")
        if a.password_hash == prior.password_hash:
            continue
        if (prior.password_hash is not None or a.password_hash is None
                or not a.source_active or a.email_verified_at is None
                or not a.password_hash.startswith(("$argon2id$", "pbkdf2_sha256$"))):
            raise IdentityMigrationConflict("Recovery is not a verified null-to-hash addition")
        additions.append(RecoveryAddition(a.subject, a.password_hash))
    return tuple(sorted(additions, key=lambda a: a.subject))


async def apply_pending_recovery_additions(connection, source: ImportBundle,
                                           approved: ApprovedInventory, *,
                                           expected_additions: int,
                                           operator_approved: bool = False) -> dict:
    """Apply a reviewed fresh encrypted snapshot on an isolated operator connection.

    Only the dedicated recovery role may execute this. Refuse all changes once
    the original pending-only fence has been removed. No activation, provider
    updates or overwrites. Never mount this function as HTTP or an agent tool.
    """
    import os
    from .pending_reconciliation import read_pending_target
    if not operator_approved or os.getenv("DRAGONZPYDER_RECOVERY_SYNC_APPROVED") != "1":
        raise PermissionError("Explicit recovery synchronization approval required")
    if type(expected_additions) is not int or not 0 <= expected_additions <= approved.accounts:
        raise IdentityMigrationConflict("Invalid approved recovery count")
    async with connection.transaction(isolation="serializable"):
        await connection.execute("SELECT pg_advisory_xact_lock(739110211)")
        if await connection.fetchval("""
            SELECT current_user='dz_identity_recovery_sync' AND session_user=current_user
               AND NOT (r.rolsuper OR r.rolcreatedb OR r.rolcreaterole
                        OR r.rolreplication OR r.rolbypassrls OR r.rolinherit)
               AND NOT EXISTS (SELECT 1 FROM pg_auth_members m WHERE m.member=r.oid)
               AND NOT EXISTS (SELECT 1 FROM pg_database d WHERE d.datname=current_database() AND d.datdba=r.oid)
               AND NOT EXISTS (SELECT 1 FROM pg_class c WHERE c.relowner=r.oid)
               AND NOT has_database_privilege(current_user,current_database(),'CREATE,TEMPORARY')
               AND NOT has_schema_privilege(current_user,'public','CREATE')
               AND NOT EXISTS (
                 SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                 WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','f')
                   AND (has_any_column_privilege(current_user,c.oid,'INSERT,REFERENCES')
                     OR has_table_privilege(current_user,c.oid,'DELETE,TRUNCATE,TRIGGER')
                     OR (c.relname<>'identity_accounts' AND has_any_column_privilege(current_user,c.oid,'UPDATE'))
                     OR (c.relname='identity_accounts' AND EXISTS (
                       SELECT 1 FROM pg_attribute a WHERE a.attrelid=c.oid AND a.attnum>0
                         AND NOT a.attisdropped AND a.attname<>'password_hash'
                         AND has_column_privilege(current_user,c.oid,a.attnum,'UPDATE')))))
               AND (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                    WHERE n.nspname='public' AND c.relname IN ('identity_accounts','identity_provider_links')
                      AND c.relrowsecurity)=2
             FROM pg_roles r WHERE r.rolname=current_user
        """) is not True:
            raise PermissionError("Dedicated restricted recovery role required")
        # read_pending_target opens its own readonly repeatable-read transaction;
        # in this serializable outer transaction use a separate validated reader.
        from .pending_reconciliation import read_pending_target_in_transaction
        target = await read_pending_target_in_transaction(connection, approved)
        additions = plan_recovery_additions(source, target, approved)
        if len(additions) != expected_additions:
            raise IdentityMigrationConflict("Recovery addition count changed")
        for item in additions:
            updated = await connection.execute("""
                UPDATE public.identity_accounts SET password_hash=$1
                WHERE subject=$2 AND source_operly_user_id=subject
                  AND identity_origin='operly_import' AND status='pending'
                  AND source_active AND email_verified_at IS NOT NULL AND password_hash IS NULL
            """, item.new_hash, item.subject)
            if updated != "UPDATE 1":
                raise IdentityMigrationConflict("Recovery target changed")
        verified = await read_pending_target_in_transaction(connection, approved)
        if plan_recovery_additions(source, verified, approved):
            raise IdentityMigrationConflict("Recovery readback mismatch")
    return {"password_additions": expected_additions, "active_accounts": 0}
