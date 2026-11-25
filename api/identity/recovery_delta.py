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
