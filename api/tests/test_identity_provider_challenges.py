"""One-time provider challenge tests; synthetic fake DB."""
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from identity.provider_challenges import create_provider_challenge, consume_provider_challenge
from identity.providers import ProviderProofDenied


class FakeDB:
    def __init__(self):
        self.data = {}
    async def execute(self, sql, *args):
        state, binding, provider, nonce, expiration = args
        self.data[state] = [binding, provider, nonce, True]
    async def fetchrow(self, sql, *args):
        state, binding, provider = args
        row = self.data.get(state)
        if not row or not row[3] or (row[0],row[1]) != (binding,provider):
            return None
        row[3] = False
        return {"nonce": row[2]}


@pytest.mark.asyncio
async def test_provider_challenge_is_browser_bound_and_single_use(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_GRANT_HASH_KEY", "h" * 48)
    db = FakeDB()
    challenge = await create_provider_challenge(db, provider="google")
    with pytest.raises(ProviderProofDenied):
        await consume_provider_challenge(db, provider="google", state=challenge.state, binding="wrong" * 10)
    result = await consume_provider_challenge(db, provider="google", state=challenge.state, binding=challenge.binding)
    assert result.nonce == challenge.nonce
    with pytest.raises(ProviderProofDenied):
        await consume_provider_challenge(db, provider="google", state=challenge.state, binding=challenge.binding)


@pytest.mark.asyncio
async def test_wrong_provider_cannot_consume_login(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_GRANT_HASH_KEY", "h" * 48)
    db = FakeDB()
    challenge = await create_provider_challenge(db, provider="discord")
    with pytest.raises(ProviderProofDenied):
        await consume_provider_challenge(db, provider="google", state=challenge.state, binding=challenge.binding)
    valid = await consume_provider_challenge(db, provider="discord", state=challenge.state, binding=challenge.binding)
    assert valid.nonce is None
