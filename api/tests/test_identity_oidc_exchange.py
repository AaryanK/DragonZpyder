"""OIDC token binding and atomic exchange, all offline synthetic identities."""
import base64
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from identity.tokens import SigningIdentity
from identity.grants import RedeemedGrant, OAuthGrantDenied
from identity.refresh import IssuedRefresh
import identity.exchange as exchange


@pytest.fixture(scope="module")
def signer():
    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption())
    return SigningIdentity("https://api.dragonzpyder.xyz", "test-key", pem)


def claims(token, signer, audience):
    jwk = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(signer.jwk()))
    return jwt.decode(token, jwk, algorithms=["RS256"], audience=audience,
                      issuer=signer.issuer)


def test_id_token_audience_nonce_at_hash_and_access_token_separation(signer):
    access = signer.issue_access_token(authenticated_subject="operly-existing-id",
                                       audience="operly-api", scope="openid operly:access")
    nonce = "synthetic-nonce-" + "x" * 24
    identity = signer.issue_id_token(authenticated_subject="operly-existing-id",
                                     client_id="operly-web", nonce=nonce, access_token=access)
    payload = claims(identity, signer, "operly-web")
    expected_at_hash = base64.urlsafe_b64encode(
        hashlib.sha256(access.encode("ascii")).digest()[:16]
    ).rstrip(b"=").decode("ascii")
    assert payload["nonce"] == nonce
    assert payload["at_hash"] == expected_at_hash
    assert payload["sub"] == "operly-existing-id"
    assert payload["token_use"] == "id"
    assert jwt.get_unverified_header(identity)["typ"] == "JWT"
    with pytest.raises(jwt.InvalidAudienceError):
        claims(identity, signer, "dragonzpyder-web")
    with pytest.raises(jwt.InvalidAudienceError):
        claims(access, signer, "operly-web")
    with pytest.raises(ValueError):
        signer.issue_id_token(authenticated_subject="operly-existing-id",
                              client_id="operly-web", nonce="short", access_token=access)


class TxDB:
    def __init__(self):
        self.active = False
        self.count = 0
    def transaction(self):
        db = self
        class Tx:
            async def __aenter__(self):
                assert not db.active
                db.active = True
                db.count += 1
            async def __aexit__(self, *args):
                db.active = False
        return Tx()


@pytest.mark.asyncio
async def test_code_exchange_signs_id_and_refresh_in_single_transaction(monkeypatch, signer):
    db = TxDB()
    nonce = "c" * 32
    async def consume(conn, **kwargs):
        assert conn.active and kwargs["in_transaction"] is True
        assert kwargs["client_id"] == "operly-web"
        return RedeemedGrant(subject="operly-existing-id", audience="operly-api",
                             scope="openid offline_access operly:access",
                             client_id="operly-web", nonce=nonce)
    async def issue(conn, **kwargs):
        assert conn.active and kwargs["in_transaction"] is True
        assert kwargs["subject"] == "operly-existing-id"
        return IssuedRefresh("r" * 64, datetime.now(timezone.utc) + timedelta(days=30))
    monkeypatch.setattr(exchange, "redeem_code", consume)
    monkeypatch.setattr(exchange, "issue_refresh", issue)
    data = await exchange.exchange_code(db, signer, code="c" * 64,
                                        client_id="operly-web", redirect_uri="https://operly.example/cb",
                                        code_verifier="v" * 45)
    assert db.count == 1 and not db.active
    assert data["refresh_token"] == "r" * 64
    assert claims(data["id_token"], signer, "operly-web")["nonce"] == nonce
    assert claims(data["access_token"], signer, "operly-api")["token_use"] == "access"


@pytest.mark.asyncio
async def test_missing_nonce_fails_before_refresh_issuance(monkeypatch, signer):
    db = TxDB()
    async def consume(conn, **kwargs):
        return RedeemedGrant(subject="operly-existing-id", audience="operly-api",
                             scope="openid offline_access", client_id="operly-web", nonce=None)
    async def should_not_issue(conn, **kwargs):
        raise AssertionError("Refresh must not be issued without nonce")
    monkeypatch.setattr(exchange, "redeem_code", consume)
    monkeypatch.setattr(exchange, "issue_refresh", should_not_issue)
    with pytest.raises(OAuthGrantDenied):
        await exchange.exchange_code(db, signer, code="c" * 64,
                                     client_id="operly-web", redirect_uri="https://operly.example/cb",
                                     code_verifier="v" * 45)
    assert not db.active


@pytest.mark.asyncio
async def test_refresh_exchange_never_returns_id_token_without_nonce(monkeypatch, signer):
    from identity.refresh import RotatedRefresh
    async def rotate(conn, **kwargs):
        assert kwargs["client_id"] == "operly-web"
        return RotatedRefresh("operly-existing-id", "operly-api",
                              "openid offline_access operly:access", "n" * 64,
                              datetime.now(timezone.utc) + timedelta(days=30))
    monkeypatch.setattr(exchange, "rotate_refresh", rotate)
    data = await exchange.exchange_refresh(TxDB(), signer, refresh_token="r" * 64,
                                           client_id="operly-web", redirect_uri="https://operly.example/cb")
    assert "id_token" not in data
    assert data["refresh_token"] == "n" * 64
    assert claims(data["access_token"], signer, "operly-api")["token_use"] == "access"
