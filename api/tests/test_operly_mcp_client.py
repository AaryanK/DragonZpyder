"""No-provider acceptance for DragonZpyder's upstream MCP adapter boundary."""
import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from agent_platform.operly_mcp_client import load_authorized_operly_mcp_tools


def test_native_mcp_adapter_applies_per_run_tool_allowlist(monkeypatch):
    from langchain_mcp_adapters import client as official_adapter
    seen = []

    class FakeClient:
        def __init__(self, configs):
            seen.append(configs)
        async def get_tools(self):
            return [
                SimpleNamespace(name="tasks.list"),
                SimpleNamespace(name="tasks.create"),
                SimpleNamespace(name="system.runtime.status"),
            ]

    monkeypatch.setenv("DRAGONZPYDER_OPERLY_MCP_ENABLED", "1")
    monkeypatch.setattr(official_adapter, "MultiServerMCPClient", FakeClient)

    demo_token = "x" * 80
    async def run():
        return await load_authorized_operly_mcp_tools(
            url="https://operly.dragonzpyder.xyz/mcp",
            access_token=demo_token,
            approved_tool_names=frozenset({"tasks.list", "system.runtime.status"}),
        )
    selected = asyncio.run(run())
    assert [item.name for item in selected] == ["operly_tasks_list", "operly_system_runtime_status"]
    assert seen[0]["operly"]["transport"] == "streamable_http"
    assert seen[0]["operly"]["url"].endswith("/mcp")
    assert seen[0]["operly"]["headers"]["Authorization"].startswith("Bearer ")


def test_native_mcp_adapter_fails_closed_on_unapproved_egress(monkeypatch):
    from langchain_mcp_adapters import client as official_adapter

    class FakeClient:
        def __init__(self, _):
            raise AssertionError("No network client should be constructed")

    monkeypatch.setattr(official_adapter, "MultiServerMCPClient", FakeClient)
    monkeypatch.delenv("DRAGONZPYDER_OPERLY_MCP_ENABLED", raising=False)

    async def load(url, token, names):
        return await load_authorized_operly_mcp_tools(
            url=url, access_token=token,
            approved_tool_names=names,
        )

    with pytest.raises(RuntimeError, match="not enabled"):
        asyncio.run(load("https://operly.dragonzpyder.xyz/mcp",
                         "t" * 44, frozenset({"tasks.list"})))
    monkeypatch.setenv("DRAGONZPYDER_OPERLY_MCP_ENABLED", "1")
    with pytest.raises(ValueError, match="not allowlisted"):
        asyncio.run(load("https://malicious.example/mcp", "t" * 44,
                         frozenset({"tasks.list"})))
    with pytest.raises(ValueError, match="not allowlisted"):
        asyncio.run(load("https://operly.dragonzpyder.xyz/other", "t" * 44,
                         frozenset({"tasks.list"})))
    with pytest.raises(ValueError, match="Invalid scoped"):
        asyncio.run(load("https://operly.dragonzpyder.xyz/mcp", "short",
                         frozenset({"tasks.list"})))
    with pytest.raises(ValueError, match="Invalid scoped"):
        asyncio.run(load("https://operly.dragonzpyder.xyz/mcp", "t" * 44,
                         frozenset()))


def test_native_mcp_adapter_rejects_discovered_privilege_escalation(monkeypatch):
    from langchain_mcp_adapters import client as official_adapter

    class FakeClient:
        def __init__(self, _):
            pass
        async def get_tools(self):
            # A server that only presents a mutating tool cannot force it into
            # a read-only agent's independently approved list.
            return [SimpleNamespace(name="tasks.create")]

    monkeypatch.setenv("DRAGONZPYDER_OPERLY_MCP_ENABLED", "1")
    monkeypatch.setattr(official_adapter, "MultiServerMCPClient", FakeClient)

    with pytest.raises(RuntimeError, match="No approved"):
        asyncio.run(load_authorized_operly_mcp_tools(
            url="https://operly.dragonzpyder.xyz/mcp",
            access_token="t" * 44,
            approved_tool_names=frozenset({"tasks.list"}),
        ))
