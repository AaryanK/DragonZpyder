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
