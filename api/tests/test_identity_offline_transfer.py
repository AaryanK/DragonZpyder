"""Synthetic-only offline transfer acceptance tests."""
import hashlib
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet, InvalidToken

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from identity.importer import prepare_snapshot
from identity.offline_transfer import seal, open_package, _write_private, _read_private, TTL_SECONDS
from identity.production_import import ApprovedInventory, read_source_snapshot
from identity.reconciliation import IdentityMigrationConflict


def sample():
    uid = str(uuid4())
    users = [{"id": uid, "email": "synthetic@example.test",
              "password_hash": None, "display_name": "Synthetic",
              "email_verified_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
              "active": True}]
    links = [{"user_id": uid, "provider": "google", "provider_subject": "synthetic-subject"}]
    return users, links


def digest(token):
    return hashlib.sha256(token).hexdigest()


def test_encrypted_roundtrip_preserves_identity_and_link():
    users, links = sample()
    bundle = prepare_snapshot(users, links, [])
    key = Fernet.generate_key()
    inventory = ApprovedInventory(1, 1)
    token = seal(bundle, inventory, 1, key)
    assert b"synthetic@example.test" not in token
    assert b"synthetic-subject" not in token
    assert open_package(token, inventory, 1, key, digest(token)) == bundle
    with pytest.raises(IdentityMigrationConflict):
        open_package(token, inventory, 0, key, digest(token))
    with pytest.raises(IdentityMigrationConflict):
        open_package(token, ApprovedInventory(2, 1), 1, key, digest(token))
    with pytest.raises(InvalidToken):
        open_package(token, inventory, 1, Fernet.generate_key(), digest(token))


def test_digest_tampering_and_expiry():
    users, links = sample()
    bundle = prepare_snapshot(users, links, [])
    key = Fernet.generate_key()
    inventory = ApprovedInventory(1, 1)
    token = seal(bundle, inventory, 0, key)
    with pytest.raises(IdentityMigrationConflict):
        open_package(token, inventory, 0, key, "0" * 64)
    changed = bytearray(token)
    changed[30] = ord("B") if changed[30] == ord("A") else ord("A")
    changed = bytes(changed)
    with pytest.raises(InvalidToken):
        open_package(changed, inventory, 0, key, digest(changed))
    f = Fernet(key)
    expired = f.encrypt_at_time(f.decrypt(token), int(time.time()) - TTL_SECONDS - 5)
    with pytest.raises(InvalidToken):
        open_package(expired, inventory, 0, key, digest(expired))


def test_private_file_exclusive_and_symlink_safe(tmp_path):
    path = tmp_path / "snapshot.enc"
    _write_private(path, b"ciphertext")
    assert path.stat().st_mode & 0o777 == 0o600
    assert _read_private(path) == b"ciphertext"
    with pytest.raises(FileExistsError):
        _write_private(path, b"replacement")
    symlink = tmp_path / "link"
    symlink.symlink_to(path)
    with pytest.raises(OSError):
        _read_private(symlink)
    os.chmod(path, 0o644)
    with pytest.raises(IdentityMigrationConflict):
        _read_private(path)


@pytest.mark.asyncio
async def test_unsupported_hash_requires_exact_recovery_inventory():
    users, links = sample()
    users[0]["password_hash"] = "$legacy$synthetic-only"

    class Source:
        def transaction(self, **kwargs):
            assert kwargs == {"isolation": "repeatable_read", "readonly": True}
            class Tx:
                async def __aenter__(self): return self
                async def __aexit__(self, *args): return False
            return Tx()
        async def fetchval(self, query): return True
        async def fetch(self, query):
            return users if "FROM public.app_users" in query else links

    inventory = ApprovedInventory(1, 1)
    with pytest.raises(IdentityMigrationConflict):
        await read_source_snapshot(Source(), inventory)
    bundle = await read_source_snapshot(Source(), inventory, expected_unsupported_passwords=1)
    assert bundle.accounts[0].password_hash is None
    assert users[0]["password_hash"] == "$legacy$synthetic-only"
    users[0]["password_hash"] = None
    with pytest.raises(IdentityMigrationConflict):
        await read_source_snapshot(Source(), inventory, expected_unsupported_passwords=1)
