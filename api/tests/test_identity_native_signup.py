"""Staged Google signup: verified provider subject, no email-based merging."""
import asyncio
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from identity.native_signup import register_native_google_account
from identity.providers import ProviderProof, ProviderProofDenied


class FakeDB:
    def __init__(self, *, linked=False, email_bound=False):
        self.linked, self.email_bound = linked, email_bound
        self.ops = []

    @asynccontextmanager
    async def transaction(self):
        yield self

    async def fetchval(self, sql, *args):
        if "FROM identity_provider_links" in sql:
            return 1 if self.linked else None
        if "FROM identity_accounts" in sql:
            return 1 if self.email_bound else None
        raise AssertionError("Unexpected query")

    async def execute(self, sql, *args):
        self.ops.append((sql, args))


def test_signup_is_disabled_and_requires_google_verified_email(monkeypatch):
    db = FakeDB()
    proof = ProviderProof("google", "google-subject", "verified@example.com")
    monkeypatch.delenv("DRAGONZPYDER_NATIVE_GOOGLE_SIGNUP_ENABLED", raising=False)
    with pytest.raises(ProviderProofDenied):
        asyncio.run(register_native_google_account(db, proof))
    monkeypatch.setenv("DRAGONZPYDER_NATIVE_GOOGLE_SIGNUP_ENABLED", "1")
    with pytest.raises(ProviderProofDenied):
        asyncio.run(register_native_google_account(
            db, ProviderProof("google", "google-subject", None)))
    assert db.ops == []


def test_native_account_registration_uses_random_identity_not_operly_uuid(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_NATIVE_GOOGLE_SIGNUP_ENABLED", "1")
    db = FakeDB()
    subject = asyncio.run(register_native_google_account(
        db, ProviderProof("google", "subject-123", "verified@example.com")))
    assert len(subject) == 36
    assert len(db.ops) == 3
    assert "native_google" in db.ops[1][0]
    assert "NULL" in db.ops[1][0]
    assert db.ops[1][1] == (subject, "verified@example.com")
    assert db.ops[2][1] == (subject, "subject-123")
    assert not any("operly" in str(args).lower() for _, args in db.ops)


@pytest.mark.parametrize("linked,email_bound", [(True, False), (False, True)])
def test_existing_provider_or_email_never_automatically_merges(monkeypatch, linked, email_bound):
    monkeypatch.setenv("DRAGONZPYDER_NATIVE_GOOGLE_SIGNUP_ENABLED", "1")
    db = FakeDB(linked=linked, email_bound=email_bound)
    with pytest.raises(ProviderProofDenied):
        asyncio.run(register_native_google_account(
            db, ProviderProof("google", "subject-123", "verified@example.com")))
    assert len(db.ops) == 1  # only the advisory-lock attempt
