import sys
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import replace
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from identity.importer import prepare_snapshot
from identity.production_import import ApprovedInventory
from identity.recovery_delta import plan_recovery_additions
from identity.reconciliation import IdentityMigrationConflict


def sample():
    u = {"id": str(uuid4()), "email": "recovery@example.test",
         "display_name": "Recovery", "password_hash": None, "active": True,
         "email_verified_at": datetime.now(timezone.utc)}
    return prepare_snapshot([u], [], [])


def changed(bundle, **kwargs):
    return replace(bundle, accounts=(replace(bundle.accounts[0], **kwargs),))


def test_recovery_addition_only():
    target = sample()
    source = changed(target,password_hash="pbkdf2_sha256$synthetic")
    approved = ApprovedInventory(1,0)
    assert not plan_recovery_additions(target,target,approved)
    result = plan_recovery_additions(source,target,approved)
    assert len(result)==1 and result[0].subject==target.accounts[0].subject
    assert "synthetic" not in repr(result)
    with pytest.raises(IdentityMigrationConflict):
        plan_recovery_additions(target,source,approved)
    with pytest.raises(IdentityMigrationConflict):
        plan_recovery_additions(changed(source,password_hash="$argon2id$other"),source,approved)


@pytest.mark.parametrize("field,value", [
    ("email","another@example.test"),("display_name","Different"),
    ("source_active",False),("email_verified_at",None),
])
def test_drift_rejected(field,value):
    target=sample()
    source=changed(target,password_hash="$argon2id$synthetic",**{field:value})
    with pytest.raises(IdentityMigrationConflict):
        plan_recovery_additions(source,target,ApprovedInventory(1,0))


def test_unverified_and_inactive_recovery_rejected():
    for target in (changed(sample(),email_verified_at=None),changed(sample(),source_active=False)):
        source=changed(target,password_hash="$argon2id$synthetic")
        with pytest.raises(IdentityMigrationConflict):
            plan_recovery_additions(source,target,ApprovedInventory(1,0))
