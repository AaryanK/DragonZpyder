"""MCP SDK adapter safety contracts. No sockets, providers or models."""
import asyncio
from types import SimpleNamespace

import pytest

from agent_platform.capability_hub import CapabilityHub, CapabilityHubError
from agent_platform.mcp_adapter import ApprovedMCPServer, bind_reviewed_remote_mcp


async def empty(_):
    return {}


def reviewed(url="https://mcp.example.com/mcp"):
    return ApprovedMCPServer("search", url, frozenset({"search_lookup"}))


def flags(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_MCP_EXPERIMENTAL_ENABLED", "1")
    monkeypatch.setenv("DRAGONZPYDER_MCP_EGRESS_FIREWALL_ENFORCED", "1")
    monkeypatch.setenv("DRAGONZPYDER_MCP_TRUSTED_HOSTS", "mcp.example.com")


def test_mcp_is_off_by_default_even_for_reviewed_hosts(monkeypatch):
    monkeypatch.delenv("DRAGONZPYDER_MCP_EXPERIMENTAL_ENABLED", raising=False)
    monkeypatch.setenv("DRAGONZPYDER_MCP_EGRESS_FIREWALL_ENFORCED", "1")
    with pytest.raises(CapabilityHubError, match="disabled"):
        asyncio.run(bind_reviewed_remote_mcp(CapabilityHub(), [reviewed()]))


@pytest.mark.parametrize("url", [
    "http://mcp.example.com/mcp",
    "https://127.0.0.1/mcp",
    "https://mcp.example.com.evil.com/mcp",
    "https://someone@mcp.example.com/mcp",
    "https://mcp.example.com/mcp?token=inline",
    "https://mcp.example.com:8443/mcp",
    "https://localhost/mcp",
])
def test_untrusted_mcp_endpoint_refused_before_network(monkeypatch, url):
    flags(monkeypatch)
    with pytest.raises(CapabilityHubError):
        asyncio.run(bind_reviewed_remote_mcp(CapabilityHub(), [reviewed(url)]))


def test_only_operator_reviewed_mcp_tools_enter_dragonzpyder_hub(monkeypatch):
    flags(monkeypatch)
    seen = []
    class FakeClient:
        def __init__(self, connections, **kwargs):
            seen.append((connections, kwargs))
        async def get_tools(self):
            return [
                SimpleNamespace(name="search_lookup", ainvoke=empty),
                SimpleNamespace(name="search_delete_all", ainvoke=empty),
            ]
    monkeypatch.setattr("langchain_mcp_adapters.client.MultiServerMCPClient", FakeClient)
    hub = asyncio.run(bind_reviewed_remote_mcp(CapabilityHub(), [reviewed()]))
    assert [x.name for x in hub.tools()] == ["search_lookup"]
    assert hub.catalog()[0]["provider"] == "mcp"
    assert seen[0][1]["tool_name_prefix"] is True
    assert seen[0][1]["handle_tool_errors"] is False


def test_required_mcp_tool_missing_fails_closed(monkeypatch):
    flags(monkeypatch)
    class EmptyClient:
        def __init__(self, *args, **kwargs): pass
        async def get_tools(self): return []
    monkeypatch.setattr("langchain_mcp_adapters.client.MultiServerMCPClient", EmptyClient)
    with pytest.raises(CapabilityHubError, match="could not be verified"):
        asyncio.run(bind_reviewed_remote_mcp(CapabilityHub(), [reviewed()]))
