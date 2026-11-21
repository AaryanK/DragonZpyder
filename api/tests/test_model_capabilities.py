"""No-network OpenRouter tool-capability preflight contracts."""
import asyncio
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_platform.model_capabilities import (
    ModelCapabilityUnavailable, parse_tool_capability, preflight_tool_model,
)


def model(id="openai/gpt-oss-120b", tools=True, context=131072):
    return {"id": id, "supported_parameters": ["max_tokens", "tools"] if tools
            else ["temperature"], "context_length": context}


def test_model_must_have_exact_slug_and_advertised_tool_support():
    profile = parse_tool_capability({"data": [model()]}, "openai/gpt-oss-120b")
    assert profile["tools"] is True
    assert profile["context_length"] >= 8192
    with pytest.raises(ModelCapabilityUnavailable, match="missing"):
        parse_tool_capability({"data": [model()]}, "other")
    with pytest.raises(ModelCapabilityUnavailable, match="no advertised"):
        parse_tool_capability({"data": [model(tools=False)]}, "openai/gpt-oss-120b")
    with pytest.raises(ModelCapabilityUnavailable, match="context"):
        parse_tool_capability({"data": [model(context=1024)]}, "openai/gpt-oss-120b")
    with pytest.raises(ModelCapabilityUnavailable, match="invalid shape"):
        parse_tool_capability([], "openai/gpt-oss-120b")


def test_preflight_uses_fixed_catalog_https_and_never_follows_redirects():
    def handler(req):
        assert req.url.scheme == "https"
        assert req.url.host == "openrouter.ai"
        assert req.url.path == "/api/v1/models"
        assert req.url.params["supported_parameters"] == "tools"
        assert req.url.params["q"] == "openai/gpt-oss-120b"
        return httpx.Response(200, json={"data": [model()]})
    async def check():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await preflight_tool_model("openai/gpt-oss-120b", client=client)
    assert asyncio.run(check())["tools"] is True


@pytest.mark.parametrize("status", [301, 404, 429, 503])
def test_preflight_unavailable_is_fail_closed(status):
    async def check():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(status))
        ) as client:
            return await preflight_tool_model("openai/gpt-oss-120b", client=client)
    with pytest.raises(ModelCapabilityUnavailable):
        asyncio.run(check())


def test_preflight_does_not_accept_unrelated_or_duplicate_model_ids():
    assert parse_tool_capability({"data": [model()]}, "openai/gpt-oss-120b")
    with pytest.raises(ModelCapabilityUnavailable):
        parse_tool_capability({"data": [model(), model()]}, "openai/gpt-oss-120b")
