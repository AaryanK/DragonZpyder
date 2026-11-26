"""First-party chat must never accept caller-selected identity or silently
enter an Operly runtime. No model, external OAuth, or PostgreSQL is used here.
"""
import asyncio
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_platform import first_party_chat as native
from main import app


def test_native_chat_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("DRAGONZPYDER_FIRST_PARTY_CHAT_ENABLED", raising=False)
    with TestClient(app) as client:
        assert client.get("/v2/personal/status").json()["web_cutover_enabled"] is False
        assert client.get("/v2/personal/conversations").status_code == 404
        assert client.post("/v2/personal/chat", json={"message": "hello"}).status_code == 404


def test_body_cannot_supply_user_or_service_credentials():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        native.ChatInput(message="hello", user_id="another-user")
    with pytest.raises(ValidationError):
        native.ChatInput(message="hello", mcp_access_token="forged")


def test_changing_origin_rejected_before_identity_db(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_FIRST_PARTY_CHAT_ENABLED", "1")
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_HTTP_ENABLED", "1")
    monkeypatch.setenv("DRAGONZPYDER_AGENTS_ENABLED", "1")
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_ISSUER", "https://api.dragonzpyder.xyz")
    request = SimpleNamespace(headers={"origin": "https://evil.example", "x-dz-csrf": "x"},
                              cookies={"__Host-dz_identity": "session"})
    with pytest.raises(HTTPException) as err:
        asyncio.run(native._owner(request, changing=True))
    assert err.value.status_code == 403


def test_user_is_resolved_from_first_party_session_not_prompt(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_FIRST_PARTY_CHAT_ENABLED", "1")
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_HTTP_ENABLED", "1")
    monkeypatch.setenv("DRAGONZPYDER_AGENTS_ENABLED", "1")
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_ISSUER", "https://api.dragonzpyder.xyz")
    @asynccontextmanager
    async def identity_db():
        yield object()
    resolve = AsyncMock(return_value="identity-owned-subject")
    monkeypatch.setattr(native, "_identity_db", identity_db)
    monkeypatch.setattr(native, "resolve_browser_session", resolve)
    request = SimpleNamespace(
        headers={"origin": "https://api.dragonzpyder.xyz", "x-dz-csrf": "csrf"},
        cookies={"__Host-dz_identity": "opaque-session"},
    )
    result = asyncio.run(native._owner(request, changing=True))
    assert result == "identity-owned-subject"
    assert resolve.await_args.kwargs == {
        "secret": "opaque-session", "csrf": "csrf", "require_csrf": True,
    }


def test_conversation_owner_check_rejects_other_user_without_disclosure():
    class DB:
        async def fetchrow(self, query, *args):
            assert "owner_id=$2" in query
            assert args[1] == "current-user"
            return None
    with pytest.raises(HTTPException) as err:
        asyncio.run(native._require_conversation(
            DB(), user="current-user", conversation_id=uuid4()))
    assert err.value.status_code == 404
    assert err.value.detail == "Conversation not found"


def test_identity_session_independent_of_native_chat_gate(monkeypatch):
    monkeypatch.delenv("DRAGONZPYDER_FIRST_PARTY_CHAT_ENABLED", raising=False)
    monkeypatch.setattr(native, "_identity_enabled", lambda: None)
    @asynccontextmanager
    async def identity_db():
        yield object()
    monkeypatch.setattr(native, "_identity_db", identity_db)
    resolver = AsyncMock(return_value="active-identity")
    monkeypatch.setattr(native, "resolve_browser_session", resolver)
    request = SimpleNamespace(cookies={"__Host-dz_identity":"opaque"})
    result = asyncio.run(native.session(request))
    assert result["authenticated"] is True
    assert result["native_chat_enabled"] is False
    resolver.assert_awaited_once()
