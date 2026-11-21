"""Provider-neutral MCP broker contracts. No external credentials or network."""
import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_platform.mcp_broker import (
    McpGrant, discover_granted_mcp_tools, invoke_granted_mcp_tool, tool_alias,
)


def grant(provider, tool, host):
    return McpGrant(
        provider_id=provider,
        url=f"https://{host}/mcp",
        allowed_hosts=frozenset({host}),
        headers={"Authorization": "Bearer sample-private-token"},
        capability_ids=frozenset({tool}),
    )


def test_two_mcp_providers_discover_without_scheduler_or_name_collision(monkeypatch):
    from langchain_mcp_adapters import client as adapter
    connections = []

    class FakeClient:
        def __init__(self, config):
            connections.append(config)
            self.provider = next(iter(config))

        async def get_tools(self):
            # Both servers offer the SAME raw capability ID.
            return [
                SimpleNamespace(name="documents.list"),
                SimpleNamespace(name="unsafe.delete"),
            ]

    monkeypatch.setattr(adapter, "MultiServerMCPClient", FakeClient)
    tools = asyncio.run(discover_granted_mcp_tools([
        grant("operly", "documents.list", "operly.example.com"),
        grant("canva", "documents.list", "canva.example.com"),
    ]))
    assert [t.name for t in tools] == [
        "operly_documents_list", "canva_documents_list",
    ]
    assert len(connections) == 2
    assert connections[0]["operly"]["transport"] == "streamable_http"
    assert connections[1]["canva"]["transport"] == "streamable_http"
    assert "sample-private-token" not in repr(grant("operly", "documents.list", "operly.example.com"))


def test_broker_refuses_unapproved_hosts_tool_names_and_bad_alias(monkeypatch):
    from langchain_mcp_adapters import client as adapter

    class FakeClient:
        def __init__(self, _):
            raise AssertionError("No client should connect when host is invalid")

    monkeypatch.setattr(adapter, "MultiServerMCPClient", FakeClient)
    bad = McpGrant(
        provider_id="canva",
        url="https://127.0.0.1/mcp",
        allowed_hosts=frozenset({"canva.example.com"}),
        headers={},
        capability_ids=frozenset({"documents.list"}),
    )
    with pytest.raises(ValueError, match="not explicitly approved"):
        asyncio.run(discover_granted_mcp_tools([bad]))
    with pytest.raises(ValueError, match="identifier"):
        tool_alias("bad provider", "documents.list")
    with pytest.raises(ValueError, match="too long"):
        tool_alias("operly", "x" * 120)


class NoArgs(BaseModel):
    pass


class RequiredArgs(BaseModel):
    doc_id: str


class VerifiedTool:
    def __init__(self, name, result, schema=NoArgs):
        self.name = name
        self.result = result
        self.schema = schema
        self.calls = 0

    def get_input_schema(self):
        return self.schema

    async def ainvoke(self, arguments):
        self.calls += 1
        return self.result


def test_invocation_receipt_proves_observed_call_and_digest():
    tool = VerifiedTool("canva_documents_list", {"documents": [1]})
    run = invoke_granted_mcp_tool(
        tools=[tool], provider_id="canva", capability_id="documents.list",
        approved_ids=frozenset({"documents.list"}),
        unattended_read_ids=frozenset({"documents.list"}),
        arguments={},
    )
    outcome = asyncio.run(run)
    assert tool.calls == 1
    assert outcome.receipt.alias == "canva_documents_list"
    assert outcome.receipt.provider_id == "canva"
    assert len(outcome.receipt.result_sha256) == 64
    assert "documents" not in repr(outcome.receipt)


def test_no_call_for_missing_grant_or_unattended_permission():
    tool = VerifiedTool("canva_documents_list", {"documents": []})
    async def check():
        with pytest.raises(PermissionError, match="signed grant"):
            await invoke_granted_mcp_tool(
                tools=[tool], provider_id="canva", capability_id="documents.list",
                approved_ids=frozenset(), arguments={},
            )
        with pytest.raises(PermissionError, match="unattended"):
            await invoke_granted_mcp_tool(
                tools=[tool], provider_id="canva", capability_id="documents.list",
                approved_ids=frozenset({"documents.list"}),
                unattended_read_ids=frozenset(), arguments={},
            )
    asyncio.run(check())
    assert tool.calls == 0


def test_schema_failure_is_never_invoked():
    tool = VerifiedTool("operly_document_get", {"ok": True}, RequiredArgs)
    async def check():
        with pytest.raises(ValueError):
            await invoke_granted_mcp_tool(
                tools=[tool], provider_id="operly", capability_id="document.get",
                approved_ids=frozenset({"document.get"}),
                unattended_read_ids=frozenset({"document.get"}), arguments={},
            )
    asyncio.run(check())
    assert tool.calls == 0


def test_provider_error_never_generates_success_receipt():
    for output in ({"isError": True}, {"ok": False},
                   {"status": "waiting_for_approval"},
                   SimpleNamespace(status="error")):
        tool = VerifiedTool("operly_tasks_list", output)
        async def check():
            with pytest.raises(RuntimeError, match="unsuccessful"):
                await invoke_granted_mcp_tool(
                    tools=[tool], provider_id="operly", capability_id="tasks.list",
                    approved_ids=frozenset({"tasks.list"}),
                    unattended_read_ids=frozenset({"tasks.list"}), arguments={},
                )
        asyncio.run(check())
        assert tool.calls == 1
