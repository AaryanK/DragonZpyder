"""Provider proof/linked-account isolation tests, no external calls."""
import sys
from pathlib import Path
import pytest
import httpx
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from identity.providers import (ProviderProof, ProviderProofDenied,
                                find_login_account, verify_google_identity_token,
                                exchange_discord_oauth_code)


class AccountDB:
    def __init__(self):
        self.calls = []
    async def fetchrow(self, sql, *args):
        self.calls.append((sql, args))
        if args == ("google", "google-sub"):
            return {"subject": "operly-u1"}
        return None


@pytest.mark.asyncio
async def test_exact_provider_subject_is_required_not_email():
    db = AccountDB()
    proof = ProviderProof("google", "google-sub", verified_email="someone@elsewhere.test")
    assert await find_login_account(db, proof) == "operly-u1"
    assert "p.source='auth'" in db.calls[0][0]
    assert "p.login_eligible=TRUE" in db.calls[0][0]
    with pytest.raises(ProviderProofDenied):
        await find_login_account(db, ProviderProof("discord", "discord-link", verified_email="someone@elsewhere.test"))
    assert db.calls[-1][1] == ("discord", "discord-link")


def test_google_unconfigured_fails_closed(monkeypatch):
    monkeypatch.delenv("DRAGONZPYDER_IDENTITY_GOOGLE_CLIENT_ID", raising=False)
    with pytest.raises(ProviderProofDenied):
        verify_google_identity_token("unverified", expected_nonce="x" * 32)


def test_google_rejects_wrong_nonce_and_issuer_even_for_matching_email(monkeypatch):
    import google.oauth2.id_token as google_tokens
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_GOOGLE_CLIENT_ID", "synthetic-google-client")
    claims = {"iss": "https://accounts.google.com", "aud": "synthetic-google-client",
              "email_verified": True, "nonce": "correct-nonce-" + "n" * 24,
              "sub": "google-sub", "email": "person@example.test", "exp": 4102444800}
    monkeypatch.setattr(google_tokens, "verify_oauth2_token", lambda *a, **kw: dict(claims))
    with pytest.raises(ProviderProofDenied):
        verify_google_identity_token("synthetic", expected_nonce="wrong-nonce-" + "x" * 24)
    claims["iss"] = "https://untrusted.invalid"
    with pytest.raises(ProviderProofDenied):
        verify_google_identity_token("synthetic", expected_nonce="correct-nonce-" + "n" * 24)
    claims["iss"] = "https://accounts.google.com"
    claims["picture"] = "https://lh3.googleusercontent.com/a/opaque=s96-c"
    assert verify_google_identity_token("synthetic", expected_nonce="correct-nonce-" + "n" * 24).profile_picture == claims["picture"]
    claims["picture"] = "https://evil.example/avatar"
    assert verify_google_identity_token("synthetic", expected_nonce="correct-nonce-" + "n" * 24).profile_picture is None
    assert verify_google_identity_token("synthetic", expected_nonce="correct-nonce-" + "n" * 24).provider_subject == "google-sub"


@pytest.mark.asyncio
async def test_discord_exchanges_code_only_with_backend_and_rejects_bad_profile(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_DISCORD_CLIENT_ID", "client-test")
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_DISCORD_CLIENT_SECRET", "s" * 40)
    redirect = "https://api.dragonzpyder.xyz/identity/v1/provider/discord/callback"
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_DISCORD_REDIRECT_URI", redirect)
    def valid(request):
        if request.url.path.endswith("/oauth2/token"):
            assert request.method == "POST"
            assert "client_secret" in request.content.decode()
            return httpx.Response(200, json={"token_type": "Bearer", "access_token": "synthetic-token", "scope": "identify"})
        if request.url.path.endswith("/users/@me"):
            assert request.headers.get("authorization") == "Bearer synthetic-token"
            return httpx.Response(200, json={"id": "123456789012345678", "username": "person"})
        raise AssertionError(request.url)
    async with httpx.AsyncClient(transport=httpx.MockTransport(valid)) as client:
        proof = await exchange_discord_oauth_code(client, code="one-time-code", redirect_uri=redirect)
        assert (proof.provider, proof.provider_subject) == ("discord", "123456789012345678")
        with pytest.raises(ProviderProofDenied):
            await exchange_discord_oauth_code(client, code="one-time-code",
                                               redirect_uri="https://evil.invalid/cb")
    def forged(request):
        if request.url.path.endswith("/oauth2/token"):
            return httpx.Response(200, json={"token_type": "Bearer", "access_token": "synthetic-token", "scope": "identify"})
        return httpx.Response(200, json={"id": "not-a-snowflake"})
    async with httpx.AsyncClient(transport=httpx.MockTransport(forged)) as client:
        with pytest.raises(ProviderProofDenied):
            await exchange_discord_oauth_code(client, code="one-time-code", redirect_uri=redirect)
