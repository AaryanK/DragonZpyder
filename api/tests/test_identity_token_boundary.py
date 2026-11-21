"""No network, no user data, no production signing keys."""
from pathlib import Path
import sys
import pytest
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from identity.tokens import SigningIdentity, IdentityIssuerUnavailable, pkce_challenge, verify_pkce_s256


@pytest.fixture
def signer():
    private = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    pem = private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption())
    return SigningIdentity("https://api.dragonzpyder.xyz", "synthetic-kid", pem)


def test_pkce_s256_rfc7636():
    verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    challenge = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
    assert pkce_challenge(verifier) == challenge
    assert verify_pkce_s256(verifier, challenge)
    assert not verify_pkce_s256(verifier + "1", challenge)
    assert not verify_pkce_s256("weak", challenge)


def test_signed_access_token_has_scoped_claims_and_public_key(signer):
    token = signer.issue_access_token(authenticated_subject="person-123", audience="operly-api", scope="operly:access")
    public = jwt.algorithms.RSAAlgorithm.from_jwk(__import__("json").dumps(signer.jwk()))
    claims = jwt.decode(token, public, algorithms=["RS256"], audience="operly-api",
                        issuer="https://api.dragonzpyder.xyz")
    assert claims["sub"] == "person-123"
    assert claims["token_use"] == "access"
    assert claims["exp"] - claims["iat"] <= 300
    assert jwt.get_unverified_header(token)["typ"] == "at+jwt"
    assert "d" not in signer.jwk()


def test_token_cannot_be_issued_with_excessive_lifetime_or_empty_subject(signer):
    with pytest.raises(ValueError):
        signer.issue_access_token(authenticated_subject="person", audience="operly-api",
                                  scope="operly:access", lifetime_seconds=3600)
    with pytest.raises(ValueError):
        signer.issue_access_token(authenticated_subject="", audience="operly-api", scope="operly:access")


def test_missing_or_weak_key_fails_closed(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_ISSUER", "http://api.dragonzpyder.xyz")
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_SIGNING_KID", "test")
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_SIGNING_KEY_PEM", "not a key")
    with pytest.raises(IdentityIssuerUnavailable):
        SigningIdentity.from_environment()
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_ISSUER", "https://api.dragonzpyder.xyz")
    with pytest.raises(IdentityIssuerUnavailable):
        SigningIdentity.from_environment()
