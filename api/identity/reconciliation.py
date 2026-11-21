"""Fail-closed reconciliation of existing Operly identity exports.

Inputs must be taken from an authorized, isolated database snapshot. No service,
password hash, connector secret or email address is sent to an agent or third party.
The module only validates an export; it does not grant authentication or mutate DBs.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping


class IdentityMigrationConflict(ValueError):
    """A snapshot cannot be imported without explicit human reconciliation."""


@dataclass(frozen=True)
class IdentityLink:
    operly_user_id: str
    provider: str
    provider_subject: str
    source: str
    login_eligible: bool


@dataclass(frozen=True)
class IdentityPlan:
    user_ids: tuple[str, ...]
    links: tuple[IdentityLink, ...]


def _required_string(record: Mapping, key: str, limit: int = 255) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not 1 <= len(value) <= limit or not value.strip():
        raise IdentityMigrationConflict(f"Invalid required {key}")
    if value != value.strip() or any(ord(ch) < 32 for ch in value):
        raise IdentityMigrationConflict(f"Invalid {key}")
    return value


def reconcile(
    users: Iterable[Mapping],
    auth_identities: Iterable[Mapping],
    external_identities: Iterable[Mapping],
) -> IdentityPlan:
    """Reject ambiguous subjects and orphaned links before any DB import.

    Input keys intentionally match Operly models. AuthIdentity represents a
    sign-in proof, while ExternalIdentity is only a linked-channel identity.
    An external account must NOT automatically become a login credential.
    """
    user_ids: set[str] = set()
    for user in users:
        uid = _required_string(user, "id", 120)
        if uid in user_ids:
            raise IdentityMigrationConflict("Duplicate Operly user ID")
        user_ids.add(uid)
    if not user_ids:
        raise IdentityMigrationConflict("No user records to reconcile")

    # One provider-subject tuple can belong to exactly one person globally.
    subjects: dict[tuple[str, str], str] = {}
    links: dict[tuple[str, str], IdentityLink] = {}

    def ingest(rows: Iterable[Mapping], *, source: str, eligible: bool) -> None:
        for row in rows:
            owner = _required_string(row, "user_id", 120)
            provider = _required_string(row, "provider", 60).lower()
            subject = _required_string(row, "provider_subject")
            if owner not in user_ids:
                raise IdentityMigrationConflict("Orphaned provider identity")
            if source == "external" and row.get("verified_at") is None:
                # Never confer identity privileges based on unverified links.
                raise IdentityMigrationConflict("Unverified external identity")
            if provider in {"password", "local"} and source == "external":
                raise IdentityMigrationConflict("Invalid external password identity")
            identity_key = (provider, subject)
            previous_owner = subjects.setdefault(identity_key, owner)
            if previous_owner != owner:
                raise IdentityMigrationConflict("Provider subject belongs to multiple users")
            key = (provider, subject)
            previous = links.get(key)
            if previous is not None and previous.source == source:
                raise IdentityMigrationConflict("Duplicate provider identity row")
            # The same human may have a verified provider sign-in record and
            # a channel linkage. Preserve one canonical provider subject and
            # prefer the explicit sign-in record; never elevate a channel link.
            if previous is None or source == "auth":
                links[key] = IdentityLink(owner, provider, subject, source, eligible)

    ingest(auth_identities, source="auth", eligible=True)
    ingest(external_identities, source="external", eligible=False)
    return IdentityPlan(
        user_ids=tuple(sorted(user_ids)),
        links=tuple(sorted(links.values(), key=lambda item: (item.source, item.provider, item.provider_subject))),
    )
