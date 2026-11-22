"""Account-aware adapter for the existing three universal MCP tools.

The signed service request supplies account aliases. No credentials or OAuth
objects go into checkpoint state or tool arguments. A new DB authorization and
token freshness check occurs before each describe/invoke, including Hatchet.
"""
from __future__ import annotations

import json
from urllib.parse import urlsplit

from .mcp_broker import (
    CatalogGrant, McpGrant, McpRunCatalog, catalog_tools,
    discover_granted_mcp_tools, input_schema, schema_digest,
    invoke_granted_mcp_tool,
)
from .mcp_connections import ConnectionDenied, OAuthConnectionManager, reviewed_providers


class ManagedMcpRunCatalog(McpRunCatalog):
    def __init__(self, entries, *, owner: str, manager: OAuthConnectionManager,
                 scheduled: bool):
        super().__init__(entries)
        self.owner = owner
        self.manager = manager
        self.scheduled = scheduled

    async def _resolve(self, provider_id: str, tool_name: str):
        # Inherited _one enforces the account/tool selection supplied by the
        # signed service; the manager then enforces database ownership, active
        # revocation, current provider manifest, and refreshed OAuth authority.
        self._one(provider_id, tool_name)
        grant = await self.manager.grant(
            owner=self.owner, alias=provider_id, capability=tool_name,
            authorized=True,
        )
        tools = await discover_granted_mcp_tools([grant], max_tools=1)
        if len(tools) != 1:
            raise ConnectionDenied("Exact selected MCP capability unavailable")
        return grant, tools[0]

    async def describe(self, provider_id: str, tool_name: str) -> dict:
        grant, tool = await self._resolve(provider_id, tool_name)
        schema = input_schema(tool)
        if len(json.dumps(schema, default=str).encode()) > 32000:
            raise ConnectionDenied("MCP tool schema too large")
        # An untrusted server may echo the received bearer credential in its
        # tool description or JSON schema. Redact before LangGraph sees it.
        token = grant.headers["Authorization"][7:]
        return {
            "provider_id": provider_id, "tool_name": tool_name,
            "description": _redact(str(getattr(tool, "description", ""))[:4000], token),
            "input_schema": _redact(schema, token),
            "schema_sha256": schema_digest(schema),
            "permission": "reviewed_read_only",
        }

    async def invoke(self, provider_id: str, tool_name: str, arguments: dict,
                     schema_sha256: str) -> dict:
        if not isinstance(schema_sha256, str) or len(schema_sha256) != 64:
            raise ValueError("Exact schema digest required")
        grant, tool = await self._resolve(provider_id, tool_name)
        outcome = await invoke_granted_mcp_tool(
            tools=[tool], provider_id=provider_id, capability_id=tool_name,
            approved_ids=grant.capability_ids, unattended_read_ids=grant.capability_ids,
            arguments=arguments, expected_schema_sha256=schema_sha256,
            timeout_seconds=30,
        )
        from dataclasses import asdict
        token = grant.headers["Authorization"][7:]
        safe = _redact(outcome.result, token)
        data = json.dumps(safe, default=str, sort_keys=True).encode("utf-8")
        truncated = len(data) > 32000
        return {
            "receipt": asdict(outcome.receipt),
            "result": data[:32000].decode("utf-8", errors="replace") if truncated else safe,
            "result_truncated": truncated, "objective_verified": False,
        }


def _redact(value, secret: str, depth: int = 0):
    if depth > 12:
        return "[truncated]"
    if isinstance(value, str):
        return value.replace(secret, "[redacted credential]") if secret else value
    if isinstance(value, dict):
        return {_redact(str(k), secret, depth + 1)[:200]: _redact(v, secret, depth + 1)
                for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact(v, secret, depth + 1) for v in value]
    return value


async def managed_catalog_tools(
    *, manager: OAuthConnectionManager, owner: str,
    selected_account_ids: list[str], scheduled: bool = False,
) -> list:
    """Only a trusted, authenticated caller may choose account IDs.

    Operly remains the authority for its OWN tools. This catalog accepts no
    Operly aliases, and supports only separately reviewed third-party reads.
    Mutating tools and unapproved human-approval transitions are NOT exposed.
    """
    if not selected_account_ids:
        return []
    if len(selected_account_ids) > 10 or len(set(selected_account_ids)) != len(selected_account_ids):
        raise ConnectionDenied("Ambiguous or excessive account selections")
    active = {
        x["connection_id"]: x
        for x in await manager.list_connections(owner) if x["status"] == "active"
    }
    reviewed = reviewed_providers()
    entries = []
    for alias in selected_account_ids:
        record = active.get(alias)
        if not record:
            raise ConnectionDenied("Selected account is not available to user")
        provider = reviewed.get(record["provider_id"])
        if not provider:
            raise ConnectionDenied("Account provider is no longer reviewed")
        names = provider.scheduled_tools if scheduled else provider.readonly_tools
        if not names:
            raise ConnectionDenied("No separately approved unattended capabilities")
        entries.append(CatalogGrant(
            McpGrant(alias, provider.mcp_url,
                     frozenset({urlsplit(provider.mcp_url).hostname}),
                     {}, frozenset(names)),
            frozenset(names), provider.description,
        ))
    return catalog_tools(ManagedMcpRunCatalog(
        entries, owner=owner, manager=manager, scheduled=scheduled,
    ))
