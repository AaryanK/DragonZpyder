"""Offline contracts for low-cost personal AI: no paid calls or real user data."""
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from personal_core.app import app
from personal_core.budget import cap_micro, hash_principal
from personal_core.identity import IdentityUnavailable, verify
from personal_core.models import choose, ModelUnavailable


def model(name, prompt="0.00000009", completion="0.00000012", context=30000):
    return {"id": name,
            "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
            "context_length": context,
            "pricing": {"prompt": prompt, "completion": completion, "request": "0"}}


def test_personal_api_starts_disabled_and_denies_chat(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_PERSONAL_ENABLED", "0")
    with TestClient(app) as client:
        status = client.get("/healthz").json()
        assert status["personal_enabled"] is False
        response = client.post("/v1/chat", json={"message": "hello"})
        assert response.status_code == 503
        assert client.get("/v1/me/budget").status_code == 503


def test_only_approved_models_and_price_ceiling():
    cheap = model("economy")
    expensive = model("high-cost", prompt="0.000005", completion="0.000008")
    pick = choose([expensive, cheap], {"economy", "high-cost"},
                  input_bytes=300, output_tokens=384)
    assert pick.model == "economy"
    assert pick.reserve_micro_usd > 0
    with pytest.raises(ModelUnavailable):
        choose([expensive], {"high-cost"}, input_bytes=300, output_tokens=384)
    with pytest.raises(ModelUnavailable):
        choose([model("unknown")], {"economy"}, input_bytes=300, output_tokens=384)
    with pytest.raises(ModelUnavailable):
        choose([model("economy", prompt="not-a-price")], {"economy"},
               input_bytes=300, output_tokens=384)


def test_cost_cap_and_user_hash_are_isolated(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_PERSONAL_ID_HASH_KEY", "h" * 56)
    monkeypatch.setenv("DRAGONZPYDER_PERSONAL_DAILY_CAP_USD", "0.03")
    assert cap_micro() == 30000
    a = hash_principal("https://issuer.example", "alice")
    b = hash_principal("https://issuer.example", "bob")
    c = hash_principal("https://other.example", "alice")
    assert len(a) == 64 and len({a, b, c}) == 3
    assert "alice" not in a
    monkeypatch.setenv("DRAGONZPYDER_PERSONAL_DAILY_CAP_USD", "500")
    with pytest.raises(RuntimeError):
        cap_micro()


def test_unprovisioned_identity_fails_closed(monkeypatch):
    monkeypatch.delenv("DRAGONZPYDER_PERSONAL_OIDC_ISSUER", raising=False)
    monkeypatch.delenv("DRAGONZPYDER_PERSONAL_OIDC_JWKS", raising=False)
    monkeypatch.delenv("DRAGONZPYDER_PERSONAL_OIDC_AUDIENCE", raising=False)
    with pytest.raises(IdentityUnavailable):
        verify("bad-token")


def test_private_personal_gateway_rejects_legacy_auth_and_missing_ledger(monkeypatch):
    from main import app as gateway
    monkeypatch.setenv("DRAGONZPYDER_PERSONAL_GATEWAY_ENABLED", "1")
    monkeypatch.setenv("DRAGONZPYDER_PERSONAL_BACKEND_TOKEN", "z" * 48)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    monkeypatch.delenv("DRAGONZPYDER_USAGE_DATABASE_URL", raising=False)
    monkeypatch.setenv("DRAGONZPYDER_USAGE_REQUIRED", "0")
    data = {"model": "openai/gpt-oss-120b",
            "messages": [{"role": "user", "content": "hello"}]}
    with TestClient(gateway) as client:
        url = "/internal/personal/v1/chat/completions"
        assert client.post(url, json=data).status_code == 401
        assert client.post(url, json=data, headers={
            "Authorization": "Bearer " + "z" * 48,
        }).status_code == 503
        assert client.post("/internal/v1/chat/completions", json=data, headers={
            "Authorization": "Bearer " + "z" * 48,
        }).status_code == 401
