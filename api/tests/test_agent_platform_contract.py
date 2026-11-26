"""Unit-level safety contracts. These do not spend model credits."""
import hashlib
import hmac
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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



def test_memory_openrouter_fallback_requires_explicit_flag(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_MEMORY_DATABASE_URL", "postgresql://user:pwd@localhost/testdb")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    monkeypatch.setenv("DRAGONZPYDER_USE_OPENROUTER_EMBEDDINGS", "1")
    monkeypatch.setenv("DRAGONZPYDER_EMBEDDING_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("DRAGONZPYDER_MEM0_LLM_MODEL", "openai/gpt-oss-120b")
    monkeypatch.setenv("DRAGONZPYDER_MEM0_EMBED_MODEL", "openai/text-embedding-3-small")
    monkeypatch.setenv("DRAGONZPYDER_EMBEDDING_DIMENSIONS", "1536")
    cfg = memory_config()
    assert cfg["embedder"]["config"]["api_key"] == "test"
    assert cfg["vector_store"]["config"]["embedding_model_dims"] == 1536
    monkeypatch.setenv("DRAGONZPYDER_EMBEDDING_BASE_URL", "https://example.org")
    with pytest.raises(RuntimeError):
        memory_config()


def test_memory_search_uses_v3_scoped_filters():
    class Store:
        def search(self, query, **kwargs):
            assert query == "test lighthouse"
            assert kwargs["filters"] == {"user_id": "dz:synthetic-test"}
            return {"results": []}
    instance = PersonalMemory.__new__(PersonalMemory)
    instance._memory = Store()
    assert instance.search(user_id="synthetic-test", query="test lighthouse") == {"results": []}


def test_scoped_transport_binds_identity_arguments_and_response_nonce(monkeypatch):
    import asyncio
    import json
    import httpx
    from agent_platform.computer import ComputerScope, ScopedComputerTransport

    key = "k" * 48
    scope = ComputerScope("personal","owner-123","task-123")
    requests = []
    last_signature = None
    replay = False

    def handler(request):
        nonlocal last_signature
        raw = request.content
        body = json.loads(raw)
        nonce = request.headers["x-operly-nonce"]
        expected = hmac.new(key.encode(), canonical(request.method,request.url.path,
            request.headers["x-operly-timestamp"],nonce,raw),hashlib.sha256).hexdigest()
        assert request.headers["x-operly-signature"] == expected
        assert body["scope"] == scope.wire()
        requests.append((request.url.path, body))
        if request.url.path.endswith("/sessions"):
            result = {"id":"sandbox-123","state":"active","private_network":False,"network_policy":"off"}
        elif request.url.path.endswith("/destroy"):
            result = {"destroyed":True}
        else:
            result = {"ok":True,"stdout":"42","exit_code":0}
        data = json.dumps(result).encode()
        signature = hmac.new(key.encode(), f"{nonce}\n200\n".encode()+data,hashlib.sha256).hexdigest()
        if replay:
            signature = last_signature
        else:
            last_signature = signature
        return httpx.Response(200,content=data,headers={"X-Operly-Signature":signature})

    client_type = httpx.AsyncClient
    monkeypatch.setattr(httpx,"AsyncClient",lambda **kwargs: client_type(
        transport=httpx.MockTransport(handler),**kwargs))
    transport = ScopedComputerTransport(base_url="https://runner.example.org",token="a"*48,signing_key=key)

    async def run():
        nonlocal replay
        box = await transport.create(scope=scope)
        await transport.execute_authorized(sandbox_id=box["id"],scope=scope,
            tool_id="python.exec",args={"code":"print(42)"})
        assert requests[-1][1]["arguments"] == {"code":"print(42)"}
        replay = True
        with pytest.raises(RuntimeError,match="signature"):
            await transport.execute_authorized(sandbox_id=box["id"],scope=scope,
                tool_id="python.exec",args={"code":"print(42)"})
        replay = False
        assert (await transport.destroy_authorized(box["id"],scope=scope))["destroyed"]
        with pytest.raises(ValueError):
            await transport.execute_authorized(sandbox_id=box["id"],scope=scope,
                tool_id="web.fetch",args={"url":"https://example.org"})

    asyncio.run(run())
    with pytest.raises(ValueError):
        ComputerScope("personal","owner-123","task-123",workspace_id="workspace-123")
    with pytest.raises(ValueError):
        ComputerScope("workspace","owner-123","task-123")
