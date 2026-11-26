"""No-network acceptance of a shared MCP template across independent providers."""
import asyncio
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_platform.mcp_broker import (
    CatalogGrant, McpGrant, McpRunCatalog, catalog_tools,
)
from agent_platform.mcp_adapter import reviewed_public_catalog_tools

SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "minLength": 1},
        "limit": {"type": "integer", "minimum": 1, "maximum": 5},
    },
    "required": ["query"],
    "additionalProperties": False,
}


def entry(provider, name="lookup", *, allowed=True):
    host = provider + ".example.com"
    return CatalogGrant(
        McpGrant(provider, "https://" + host + "/mcp", frozenset({host}),
                 {}, frozenset({name})),
        frozenset({name}) if allowed else frozenset(),
        "Search document archives",
    )


class FakeTool:
    description = "Find matching records."
    def __init__(self, provider, name, calls, schema, result):
        self.provider, self.name, self.calls = provider, name, calls
        self.args_schema, self.result = schema, result

    async def ainvoke(self, arguments):
        self.calls.append((self.provider, arguments))
        return self.result


@pytest.fixture
def sdk(monkeypatch):
    discoveries, calls = [], []
    state = {"schema": SCHEMA, "result": {"records": [1]}}
    class Client:
        def __init__(self, config):
            self.provider = next(iter(config))
            discoveries.append(self.provider)

        async def get_tools(self):
            return [FakeTool(self.provider, name, calls, state["schema"], state["result"])
                    for name in ("lookup", "get.item", "get_item", "GetRecord", "delete")]
    monkeypatch.setattr("langchain_mcp_adapters.client.MultiServerMCPClient", Client)
    return discoveries, calls, state


def test_bounded_search_of_thousand_connections_does_not_discover_every_server(sdk):
    discoveries, calls, _ = sdk
    catalog = McpRunCatalog([entry("provider" + str(i)) for i in range(1000)])
    result = catalog.search("lookup", limit=20)
    assert len(result) == 20
    assert discoveries == calls == []
    assert [t.name for t in catalog_tools(catalog)] == [
        "search_tools", "describe_tool", "invoke_tool",
    ]


def test_shared_template_two_independent_providers_and_same_tool_name(sdk):
    discoveries, calls, _ = sdk
    catalog = McpRunCatalog([entry("archive"), entry("library")])
    async def run():
        for provider in ("archive", "library"):
            info = await catalog.describe(provider, "lookup")
            assert info["input_schema"] == SCHEMA
            result = await catalog.invoke(
                provider, "lookup", {"query": "physics"}, info["schema_sha256"],
            )
            assert result["receipt"]["provider_id"] == provider
            assert result["receipt"]["capability_id"] == "lookup"
            assert len(result["receipt"]["result_sha256"]) == 64
            assert result["result"] == {"records": [1]}
            assert result["objective_verified"] is False
    asyncio.run(run())
    assert discoveries == ["archive", "archive", "library", "library"]
    assert calls == [("archive", {"query": "physics"}), ("library", {"query": "physics"})]


def test_exact_identities_disambiguate_colliding_legacy_aliases(sdk):
    grant = entry("archive", "get.item").grant
    names = frozenset({"get.item", "get_item", "GetRecord"})
    catalog = McpRunCatalog([CatalogGrant(
        McpGrant(grant.provider_id, grant.url, grant.allowed_hosts, {}, names), names
    )])
    async def run():
        for name in sorted(names):
            info = await catalog.describe("archive", name)
            result = await catalog.invoke("archive", name, {"query": "q"}, info["schema_sha256"])
            assert result["receipt"]["capability_id"] == name
    asyncio.run(run())
    assert len(sdk[1]) == 3


def test_schema_changes_and_invalid_json_schema_arguments_do_not_execute(sdk):
    _, calls, state = sdk
    catalog = McpRunCatalog([entry("archive")])
    async def run():
        info = await catalog.describe("archive", "lookup")
        for bad in ({}, {"query": ""}, {"query": "q", "limit": 6},
                    {"query": "q", "limit": "2"}, {"query": "q", "extra": True}):
            with pytest.raises(ValueError):
                await catalog.invoke("archive", "lookup", bad, info["schema_sha256"])
        state["schema"] = {**SCHEMA, "required": ["query", "limit"]}
        with pytest.raises(ValueError, match="schema changed"):
            await catalog.invoke("archive", "lookup", {"query": "q"}, info["schema_sha256"])
    asyncio.run(run())
    assert calls == []


def test_unapproved_provider_or_tool_is_rejected_before_discovery(sdk):
    discoveries, calls, _ = sdk
    catalog = McpRunCatalog([entry("archive"), entry("library", allowed=False)])
    async def run():
        for provider, tool in (("unknown", "lookup"), ("archive", "delete"),
                               ("library", "lookup")):
            with pytest.raises(PermissionError):
                await catalog.describe(provider, tool)
            with pytest.raises(PermissionError):
                await catalog.invoke(provider, tool, {"query": "x"}, "a" * 64)
    asyncio.run(run())
    assert discoveries == calls == []


@pytest.mark.parametrize("result", [
    [{"type": "text", "text": '{"status":"waiting_for_approval"}'}],
    {"structuredContent": {"status": "denied"}},
    {"isError": True},
    '{"ok":false}',
])
def test_structured_mcp_failures_never_receive_completion_receipt(sdk, result):
    _, calls, state = sdk
    state["result"] = result
    catalog = McpRunCatalog([entry("archive")])
    async def run():
        info = await catalog.describe("archive", "lookup")
        with pytest.raises(RuntimeError, match="unsuccessful"):
            await catalog.invoke("archive", "lookup", {"query": "q"}, info["schema_sha256"])
    asyncio.run(run())
    assert len(calls) == 1


def test_manifest_catalog_requires_explicit_egress_and_operator_review(monkeypatch, sdk):
    for flag in ("DRAGONZPYDER_MCP_PERSONAL_PUBLIC_CATALOG_ENABLED",
                 "DRAGONZPYDER_MCP_EXPERIMENTAL_ENABLED",
                 "DRAGONZPYDER_MCP_EGRESS_FIREWALL_ENFORCED"):
        monkeypatch.delenv(flag, raising=False)
    assert reviewed_public_catalog_tools() == []
    monkeypatch.setenv("DRAGONZPYDER_MCP_PERSONAL_PUBLIC_CATALOG_ENABLED", "1")
    with pytest.raises(RuntimeError, match="egress"):
        reviewed_public_catalog_tools()
    for flag in ("DRAGONZPYDER_MCP_EXPERIMENTAL_ENABLED",
                 "DRAGONZPYDER_MCP_EGRESS_FIREWALL_ENFORCED"):
        monkeypatch.setenv(flag, "1")
    monkeypatch.setenv("DRAGONZPYDER_MCP_TRUSTED_HOSTS", "archive.example.com,library.example.com")
    rows = [{"provider_id": p, "url": "https://" + p + ".example.com/mcp",
             "readonly_tools": ["lookup"]} for p in ("archive", "library")]
    monkeypatch.setenv("DRAGONZPYDER_MCP_PUBLIC_CATALOG_JSON", json.dumps(rows))
    tools = {t.name: t for t in reviewed_public_catalog_tools()}
    assert set(tools) == {"search_tools", "describe_tool", "invoke_tool"}
    assert len(tools["search_tools"].invoke({"query": "lookup"})) == 2
    assert sdk[0] == []
    rows[1]["url"] = "https://unreviewed.example.com/mcp"
    monkeypatch.setenv("DRAGONZPYDER_MCP_PUBLIC_CATALOG_JSON", json.dumps(rows))
    with pytest.raises(RuntimeError, match="Invalid reviewed"):
        reviewed_public_catalog_tools()


def test_actual_langchain_tool_message_preserves_structured_mcp_content():
    from langchain_core.tools import StructuredTool
    from agent_platform.mcp_broker import invoke_granted_mcp_tool
    async def lookup(query: str):
        return ([{"type": "text", "text": "found record"}],
                {"structured_content": {"records": [{"id": "record-1"}]}})
    tool = StructuredTool.from_function(
        coroutine=lookup, name="archive_lookup", description="Search records",
        response_format="content_and_artifact",
    )
    outcome = asyncio.run(invoke_granted_mcp_tool(
        tools=[tool], provider_id="archive", capability_id="lookup",
        approved_ids=frozenset({"lookup"}), arguments={"query": "test"},
    ))
    assert outcome.result["structuredContent"]["records"][0]["id"] == "record-1"
    assert outcome.receipt.started_at and outcome.receipt.finished_at
    assert len(outcome.receipt.schema_sha256) == 64


def test_actual_langchain_artifact_failure_is_not_success():
    from langchain_core.tools import StructuredTool
    from agent_platform.mcp_broker import invoke_granted_mcp_tool
    async def lookup(query: str):
        return ("pending", {"structured_content": {"status": "waiting_for_approval"}})
    tool = StructuredTool.from_function(
        coroutine=lookup, name="archive_lookup", description="Search records",
        response_format="content_and_artifact",
    )
    with pytest.raises(RuntimeError, match="unsuccessful"):
        asyncio.run(invoke_granted_mcp_tool(
            tools=[tool], provider_id="archive", capability_id="lookup",
            approved_ids=frozenset({"lookup"}), arguments={"query": "test"},
        ))


def test_normalized_ranker_handles_plural_camel_case_and_abstains_on_ambiguity():
    from agent_platform.tool_relevance import rank_candidates, direct_candidates
    entries = [("archive", "Document storage", ["listDocuments", "workflow.list"]),
               ("calendar", "Calendar", ["listEvents"])]
    assert rank_candidates("show my workflows", entries)[0].tool_name == "workflow.list"
    assert direct_candidates("list documents", entries)[0].tool_name == "listDocuments"
    assert direct_candidates("delete documents", entries) == []
    assert direct_candidates("hello there", entries) == []
    assert direct_candidates("list workflows", [
        ("one", "", ["workflow.list"]), ("two", "", ["workflow.list"])]) == []


def test_direct_prefetch_does_not_execute_or_remove_lazy_fallback():
    from agent_platform.mcp_managed_catalog import direct_read_tools

    class Catalog(McpRunCatalog):
        async def describe(self, provider_id, tool_name):
            raise RuntimeError("synthetic unavailable")
        async def invoke(self, *args, **kwargs):
            raise AssertionError("Prefetch must not execute")

    catalog = Catalog([entry("archive", "document.list")])
    assert asyncio.run(direct_read_tools(catalog, "list documents")) == []
    assert [t.name for t in catalog_tools(catalog)] == [
        "search_tools","describe_tool","invoke_tool"]
