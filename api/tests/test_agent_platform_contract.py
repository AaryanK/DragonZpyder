"""Unit-level safety contracts. These do not spend model credits."""
import hashlib
import hmac

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from agent_platform.router import AgentPrompt, authenticated_service
from agent_platform.computer import ComputerTransport, canonical
from agent_platform.memory import memory_config, PersonalMemory


def test_internal_token_is_not_a_browser_cookie(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_AGENT_SERVICE_TOKEN", "x" * 44)
    assert authenticated_service("Bearer " + "x" * 44) == "agent-smoke"
    with pytest.raises(HTTPException):
        authenticated_service("Bearer " + "wrong" * 10)
    with pytest.raises(HTTPException):
        authenticated_service("")


def test_agent_request_is_bounded():
    AgentPrompt(thread_id="smoke-1", prompt="Hello")
    with pytest.raises(ValidationError):
        AgentPrompt(thread_id="../private", prompt="Hello")
    with pytest.raises(ValidationError):
        AgentPrompt(thread_id="thread", prompt="x" * 12001)


def test_runner_signatures_match_protocol():
    raw = b'{"networkPolicy":"off"}'
    signed = canonical("POST", "/v1/computer/sessions", "1000000000000", "a1b2", raw)
    expected = b"POST\n/v1/computer/sessions\n1000000000000\na1b2\n" + raw
    assert signed == expected
    transport = ComputerTransport(
        base_url="http://runner.railway.internal:3000",
        token="a" * 44,
        signing_key="b" * 44,
    )
    assert transport._signature(signed) == hmac.new(
        b"b" * 44, expected, hashlib.sha256
    ).hexdigest()
    with pytest.raises(ValueError):
        ComputerTransport(
            base_url="http://public.example.com",
            token="a" * 44, signing_key="b" * 44,
        )


def test_memory_fails_closed_without_config(monkeypatch):
    monkeypatch.delenv("DRAGONZPYDER_MEMORY_DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError):
        memory_config()
    with pytest.raises(ValueError):
        PersonalMemory._principal("../another-user")
