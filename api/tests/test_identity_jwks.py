"""Public JWKS must never reveal signing material or run without opt-in."""
import sys
from pathlib import Path
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from identity.router import router

app = FastAPI()
app.include_router(router)


def test_jwks_disabled_without_explicit_opt_in(monkeypatch):
    monkeypatch.delenv("DRAGONZPYDER_IDENTITY_JWKS_ENABLED", raising=False)
    with TestClient(app) as c:
        assert c.get("/.well-known/jwks.json").status_code == 404


def test_jwks_exposes_public_only(monkeypatch):
    private = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    pem = private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption()).decode()
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_JWKS_ENABLED", "1")
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_ISSUER", "https://api.dragonzpyder.xyz")
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_SIGNING_KID", "test-key")
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_SIGNING_KEY_PEM", pem)
    with TestClient(app) as c:
        response = c.get("/.well-known/jwks.json")
    assert response.status_code == 200
    jwk = response.json()["keys"][0]
    assert jwk["kid"] == "test-key"
    assert jwk["alg"] == "RS256"
    assert set(jwk) == {"kty", "use", "kid", "alg", "n", "e"}
    assert "PRIVATE KEY" not in response.text


def test_jwks_misconfiguration_fails_closed(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_JWKS_ENABLED", "1")
    monkeypatch.delenv("DRAGONZPYDER_IDENTITY_SIGNING_KEY_PEM", raising=False)
    with TestClient(app) as c:
        assert c.get("/.well-known/jwks.json").status_code == 503
