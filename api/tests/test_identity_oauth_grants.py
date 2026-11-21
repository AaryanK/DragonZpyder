"""Offline OAuth authorization-code tests. Synthetic principals and fake DB only."""
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from identity.tokens import pkce_challenge
from identity.grants import authorize_code, redeem_code, OAuthGrantDenied

VERIFIER = "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGH"
REDIRECT = "https://operly.dragonzpyder.xyz/auth/callback"


class FakeDB:
    def __init__(self):
        self.codes = {}
        self.active = {"existing-operly-id"}
        self.clients = {"operly-web": {
            "client_id": "operly-web", "redirect_uri": REDIRECT,
            "audience": "operly-api", "allowed_scope": "operly:access",
        }}
    def transaction(self):
        class Tx:
            async def __aenter__(self): return self
            async def __aexit__(self, *exc): return False
        return Tx()
    async def fetchrow(self, query, *args):
        if "FROM identity_oauth_clients" in query:
            return self.clients.get(args[0])
        if "FROM identity_authorization_codes" in query:
            return self.codes.get(args[0])
        raise AssertionError(query)
    async def fetchval(self, query, *args):
        if "FROM identity_accounts" in query:
            return 1 if args[0] in self.active else None
        raise AssertionError(query)
    async def execute(self, query, *args):
        if "INSERT INTO identity_authorization_codes" in query:
            digest, subject, client, redirect, challenge, scope, audience, deadline = args
            self.codes[digest] = {
                "subject": subject, "client_id": client, "redirect_uri": redirect,
                "pkce_s256": challenge, "scope": scope, "audience": audience,
                "expires_at": deadline, "consumed_at": None,
            }
            return "INSERT 0 1"
        if "UPDATE identity_authorization_codes" in query:
            row = self.codes[args[0]]
            if row["consumed_at"] is not None:
                return "UPDATE 0"
            row["consumed_at"] = datetime.now(timezone.utc)
            return "UPDATE 1"
        raise AssertionError(query)


@pytest.mark.asyncio
async def test_valid_single_use_code(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_GRANT_HASH_KEY", "g" * 48)
    db = FakeDB()
    issued = await authorize_code(
        db, authenticated_subject="existing-operly-id", client_id="operly-web",
        redirect_uri=REDIRECT, scope="operly:access", pkce_s256=pkce_challenge(VERIFIER),
    )
    assert issued.code
    granted = await redeem_code(db, code=issued.code, client_id="operly-web",
                                redirect_uri=REDIRECT, pkce_verifier=VERIFIER)
    assert (granted.subject, granted.audience, granted.scope) == (
        "existing-operly-id", "operly-api", "operly:access",
    )
    with pytest.raises(OAuthGrantDenied):
        await redeem_code(db, code=issued.code, client_id="operly-web",
                          redirect_uri=REDIRECT, pkce_verifier=VERIFIER)


@pytest.mark.asyncio
async def test_wrong_pkce_or_redirect_does_not_redeem(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_GRANT_HASH_KEY", "g" * 48)
    db = FakeDB()
    issued = await authorize_code(
        db, authenticated_subject="existing-operly-id", client_id="operly-web",
        redirect_uri=REDIRECT, scope="operly:access", pkce_s256=pkce_challenge(VERIFIER),
    )
    with pytest.raises(OAuthGrantDenied):
        await redeem_code(db, code=issued.code, client_id="operly-web",
                          redirect_uri=REDIRECT, pkce_verifier=VERIFIER[::-1])
    with pytest.raises(OAuthGrantDenied):
        await redeem_code(db, code=issued.code, client_id="operly-web",
                          redirect_uri="https://evil.example/cb", pkce_verifier=VERIFIER)
    assert (await redeem_code(db, code=issued.code, client_id="operly-web",
                             redirect_uri=REDIRECT, pkce_verifier=VERIFIER)).subject == "existing-operly-id"


@pytest.mark.asyncio
async def test_account_and_client_are_rechecked(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_GRANT_HASH_KEY", "g" * 48)
    db = FakeDB()
    with pytest.raises(OAuthGrantDenied):
        await authorize_code(db, authenticated_subject="unknown", client_id="operly-web",
                             redirect_uri=REDIRECT, scope="operly:access",
                             pkce_s256=pkce_challenge(VERIFIER))
    with pytest.raises(OAuthGrantDenied):
        await authorize_code(db, authenticated_subject="existing-operly-id",
                             client_id="operly-web", redirect_uri=REDIRECT,
                             scope="dragonzpyder:admin", pkce_s256=pkce_challenge(VERIFIER))
    issued = await authorize_code(db, authenticated_subject="existing-operly-id",
                                  client_id="operly-web", redirect_uri=REDIRECT,
                                  scope="operly:access", pkce_s256=pkce_challenge(VERIFIER))
    db.active.clear()
    with pytest.raises(OAuthGrantDenied):
        await redeem_code(db, code=issued.code, client_id="operly-web",
                          redirect_uri=REDIRECT, pkce_verifier=VERIFIER)


@pytest.mark.asyncio
async def test_expired_grant_and_invalid_redirect_rejected(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_GRANT_HASH_KEY", "g" * 48)
    db = FakeDB()
    issued = await authorize_code(
        db, authenticated_subject="existing-operly-id", client_id="operly-web",
        redirect_uri=REDIRECT, scope="operly:access", pkce_s256=pkce_challenge(VERIFIER),
    )
    next(iter(db.codes.values()))["expires_at"] = datetime.now(timezone.utc) - timedelta(seconds=1)
    with pytest.raises(OAuthGrantDenied):
        await redeem_code(db, code=issued.code, client_id="operly-web",
                          redirect_uri=REDIRECT, pkce_verifier=VERIFIER)
    with pytest.raises(OAuthGrantDenied):
        await authorize_code(db, authenticated_subject="existing-operly-id",
                             client_id="operly-web", redirect_uri="http://operly.example/cb",
                             scope="operly:access", pkce_s256=pkce_challenge(VERIFIER))
