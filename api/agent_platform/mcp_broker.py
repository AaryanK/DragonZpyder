"""Provider-neutral MCP discovery and execution boundary.

Both live chat and scheduled Personal runs use the *same* SDK-adapted
LangChain tools. Hatchet never needs to know an MCP provider's name or
transport. Only trusted service code constructs grants; the model receives
tool schemas but cannot choose connection URLs or bearer credentials.

This does not grant unattended mutation permission. That decision belongs to
the separate authorization/policy layer and must be renewed at execution.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import hashlib
import json
import os
import re
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit

_PROVIDER = re.compile(r"^[a-z][a-z0-9_-]{0,30}$")
_CAPABILITY = re.compile(r"^[a-z][a-z0-9_.:-]{1,159}$")
_ALIAS = re.compile(r"^[a-z][a-z0-9_]{1,63}$")


@dataclass(frozen=True, repr=False)
class McpGrant:
    """A trusted, already-authorized connection snapshot.

    Headers may contain short-lived secrets: never serialize or checkpoint a
    McpGrant. Renewable identity authority lives in the issuer, not here.
    """
    provider_id: str
    url: str
    allowed_hosts: frozenset[str]
    headers: Mapping[str, str]
    capability_ids: frozenset[str]


@dataclass(frozen=True)
class ToolReceipt:
    provider_id: str
    capability_id: str
    alias: str
    arguments_sha256: str
    result_sha256: str
    status: str = "completed"


@dataclass(frozen=True)
class ToolOutcome:
    receipt: ToolReceipt
    result: Any


def tool_alias(provider_id: str, capability_id: str) -> str:
    """Stable, model-safe alias. No provider-specific switch statements."""
    if not _PROVIDER.fullmatch(provider_id) or not _CAPABILITY.fullmatch(capability_id):
        raise ValueError("Invalid MCP provider/capability identifier")
    alias = provider_id + "_" + re.sub(r"[.:-]", "_", capability_id)
    if not _ALIAS.fullmatch(alias):
        raise ValueError("MCP tool alias is invalid or too long")
    return alias


def _connection(grant: McpGrant) -> dict:
    if not _PROVIDER.fullmatch(grant.provider_id):
        raise ValueError("Invalid MCP provider identifier")
    p = urlsplit(grant.url)
    host = (p.hostname or "").lower()
    public = p.scheme == "https" and p.port in (None, 443)
    staging_private = (
        os.getenv("DRAGONZPYDER_STAGE") == "staging"
        and p.scheme == "http" and host.endswith(".railway.internal")
        and p.port in (None, 8080)
    )
    if (not (public or staging_private) or host not in grant.allowed_hosts
            or not p.path or p.path == "/" or p.username or p.password
            or p.query or p.fragment):
        raise ValueError("MCP endpoint is not explicitly approved")
    if (not 1 <= len(grant.capability_ids) <= 40
            or any(not _CAPABILITY.fullmatch(x) for x in grant.capability_ids)):
        raise ValueError("Invalid MCP capability grant")
    if any(not isinstance(k, str) or not isinstance(v, str)
           or "\r" in k or "\n" in k or "\r" in v or "\n" in v
           for k, v in grant.headers.items()):
        raise ValueError("Invalid MCP connection headers")
    return {
        "url": grant.url,
        "transport": "streamable_http",
        "headers": dict(grant.headers),
    }


async def discover_granted_mcp_tools(
    grants: Sequence[McpGrant], *, max_tools: int = 20,
) -> list:
    """Discover only signer-authorized capabilities on trusted servers.

    One client per server keeps origins unambiguous even if two MCP providers
    advertise identically named tool IDs. The scheduler is not involved.
    """
    if not grants or not 1 <= max_tools <= 40:
        raise ValueError("Invalid MCP discovery configuration")
    from langchain_mcp_adapters.client import MultiServerMCPClient

    selected = []
    aliases: set[str] = set()
    providers: set[str] = set()
    for grant in grants:
        if grant.provider_id in providers:
            raise ValueError("Duplicate MCP provider in same grant")
        providers.add(grant.provider_id)
        client = MultiServerMCPClient({
            grant.provider_id: _connection(grant),
        })
        discovered = await client.get_tools()
        seen: set[str] = set()
        for item in discovered:
            capability = getattr(item, "name", None)
            if capability not in grant.capability_ids:
                continue
            if capability in seen:
                raise ValueError("Duplicate MCP tool name")
            seen.add(capability)
            alias = tool_alias(grant.provider_id, capability)
            if alias in aliases:
                raise ValueError("Ambiguous MCP tool alias")
            aliases.add(alias)
            # The upstream MCP adapter's closure continues to invoke the
            # original server-side capability ID, not this agent-facing alias.
            item.name = alias
            selected.append(item)
            if len(selected) > max_tools:
                raise RuntimeError("MCP tool budget exceeded")
    if not selected:
        raise RuntimeError("No approved MCP tools were available")
    return selected


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, default=str, ensure_ascii=False).encode("utf-8")


def _tool_failed(value: Any) -> bool:
    if getattr(value, "status", None) == "error":
        return True
    if getattr(value, "isError", False) is True:
        return True
    if isinstance(value, dict):
        if value.get("isError") is True or value.get("ok") is False:
            return True
        if value.get("status") in ("error", "failed", "approval_required", "waiting_for_approval"):
            return True
    # A LangChain/MCP adapter may deliver a content list.
    if isinstance(value, list):
        return any(_tool_failed(item) for item in value)
    return False


async def invoke_granted_mcp_tool(
    *, tools: Sequence, provider_id: str, capability_id: str,
    approved_ids: frozenset[str], arguments: dict,
    unattended_read_ids: frozenset[str] | None = None,
    timeout_seconds: int = 18,
) -> ToolOutcome:
    """Invoke the same adapted tool callable used by chat agents.

    A returned ToolReceipt is derived from a completed actual invocation,
    never inferred from model prose or a successful HTTP response alone.
    """
    if capability_id not in approved_ids:
        raise PermissionError("MCP tool is outside this signed grant")
    if unattended_read_ids is not None and capability_id not in unattended_read_ids:
        raise PermissionError("MCP tool has no unattended read authorization")
    if type(arguments) is not dict:
        raise ValueError("MCP tool arguments must be an object")
    data = _json_bytes(arguments)
    if len(data) > 16000:
        raise ValueError("MCP tool arguments exceed execution bound")
    alias = tool_alias(provider_id, capability_id)
    matched = [tool for tool in tools if getattr(tool, "name", None) == alias]
    if len(matched) != 1:
        raise ValueError("Authorized MCP tool not discovered uniquely")
    selected = matched[0]
    schema_fn = getattr(selected, "get_input_schema", None)
    if callable(schema_fn):
        schema = schema_fn()
        if hasattr(schema, "model_validate"):
            schema.model_validate(arguments)
        else:
            required = schema.model_json_schema().get("required", [])
            if any(key not in arguments for key in required):
                raise ValueError("Scheduled MCP call requires missing arguments")
    if not 1 <= timeout_seconds <= 120:
        raise ValueError("Invalid MCP execution timeout")

    result = await asyncio.wait_for(selected.ainvoke(arguments), timeout=timeout_seconds)
    if _tool_failed(result):
        raise RuntimeError("MCP provider returned an unsuccessful tool result")
    receipt = ToolReceipt(
        provider_id=provider_id,
        capability_id=capability_id,
        alias=alias,
        arguments_sha256=hashlib.sha256(data).hexdigest(),
        result_sha256=hashlib.sha256(_json_bytes(result)).hexdigest(),
    )
    return ToolOutcome(receipt=receipt, result=result)
