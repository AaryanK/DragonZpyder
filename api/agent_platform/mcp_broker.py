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
_CAPABILITY = re.compile(r"^[A-Za-z0-9_.:-]{1,160}$")
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
    """Preserve established aliases; hash names that do not fit legacy aliases.

    The durable identity remains the exact (provider_id, capability_id) pair.
    A collision among legacy aliases fails closed at direct binding; the lazy
    catalog resolves exact identities separately instead of guessing aliases.
    """
    if not _PROVIDER.fullmatch(provider_id) or not _CAPABILITY.fullmatch(capability_id):
        raise ValueError("Invalid MCP provider/capability identifier")
    alias = provider_id + "_" + re.sub(r"[.:-]", "_", capability_id)
    if _ALIAS.fullmatch(alias):
        return alias
    digest = hashlib.sha256((provider_id + "\0" + capability_id).encode()).hexdigest()[:24]
    return provider_id + "_mcp_" + digest


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


def _tool_failed(value: Any, *, _depth: int = 0) -> bool:
    """Recognize protocol failure and structured business failure envelopes.

    MCP content may arrive as a list of text blocks via the SDK. Only parse
    bounded JSON objects/arrays, never natural language or arbitrary code.
    A business payload may have its own status vocabulary; unknown status
    does not prove objective completion, even when transport succeeded.
    """
    if _depth > 8:
        return False
    if getattr(value, "status", None) == "error":
        return True
    if getattr(value, "isError", False) is True:
        return True
    if isinstance(value, dict):
        if value.get("isError") is True or value.get("ok") is False:
            return True
        if value.get("status") in ("error", "failed", "approval_required",
                                   "waiting_for_approval", "denied", "blocked"):
            return True
        if value.get("type") == "text":
            return _tool_failed(value.get("text"), _depth=_depth + 1)
        for key in ("structuredContent", "content"):
            if key in value and _tool_failed(value[key], _depth=_depth + 1):
                return True
    if isinstance(value, list):
        return any(_tool_failed(item, _depth=_depth + 1) for item in value)
    if isinstance(value, str) and len(value) <= 100000 and value.lstrip()[:1] in ("{", "["):
        try:
            decoded = json.loads(value)
        except ValueError:
            return False
        return _tool_failed(decoded, _depth=_depth + 1)
    return False


def input_schema(tool: Any) -> dict:
    """Use the actual MCP JSON schema, not a lossy inferred Pydantic model."""
    raw = getattr(tool, "args_schema", None)
    if isinstance(raw, dict):
        return raw
    schema_fn = getattr(tool, "get_input_schema", None)
    if not callable(schema_fn):
        raise ValueError("MCP tool input schema unavailable")
    schema = schema_fn()
    if isinstance(schema, dict):
        return schema
    if hasattr(schema, "model_json_schema"):
        return schema.model_json_schema()
    raise ValueError("MCP tool input schema unavailable")


def schema_digest(schema: dict) -> str:
    return hashlib.sha256(_json_bytes(schema)).hexdigest()


def validate_arguments(tool: Any, arguments: dict) -> None:
    raw = getattr(tool, "args_schema", None)
    schema_fn = getattr(tool, "get_input_schema", None)
    if not isinstance(raw, dict) and callable(schema_fn):
        schema_model = schema_fn()
        if hasattr(schema_model, "model_validate"):
            schema_model.model_validate(arguments)
            return
    schema = input_schema(tool)
    from jsonschema.validators import validator_for
    from referencing import Registry
    validator = validator_for(schema)
    validator.check_schema(schema)
    # Never fetch a remote reference while validating model-controlled input.
    try:
        validator(schema, registry=Registry()).validate(arguments)
    except Exception as error:
        raise ValueError("MCP arguments do not satisfy the advertised schema") from error


async def invoke_granted_mcp_tool(
    *, tools: Sequence, provider_id: str, capability_id: str,
    approved_ids: frozenset[str], arguments: dict,
    unattended_read_ids: frozenset[str] | None = None,
    timeout_seconds: int = 18,
    expected_schema_sha256: str | None = None,
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
    if expected_schema_sha256 is not None:
        if schema_digest(input_schema(selected)) != expected_schema_sha256:
            raise ValueError("MCP tool schema changed; describe again before invocation")
    validate_arguments(selected, arguments)
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
