"""Operator-reviewed remote MCP adapters for DragonZpyder's capability hub.

No user-provided endpoints, arbitrary stdio commands or auto-installation.
This is an off-by-default adapter, not a general permission to execute tools:
each server, hostname and tool name needs an independently reviewed allowlist.
An enforcing egress firewall is REQUIRED for enabled deployments.
"""
from __future__ import annotations

import asyncio
import ipaddress
import json
import os
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from .capability_hub import CapabilityHub, CapabilityHubError
from .mcp_broker import (CatalogGrant, McpGrant, McpRunCatalog,
                         catalog_tools, discover_granted_mcp_tools)

_SERVER = re.compile(r"^[a-z][a-z0-9_-]{1,31}$")
_TOOL = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{0,79}$")


@dataclass(frozen=True)
class ApprovedMCPServer:
    name: str
    url: str
    allowed_readonly_tools: frozenset[str]


def _require_reviewed_server(manifest: ApprovedMCPServer) -> None:
    if not _SERVER.fullmatch(manifest.name):
        raise CapabilityHubError("MCP server name is invalid")
    parsed = urlsplit(manifest.url)
    approved_hosts = {x.strip().lower() for x in
                      os.getenv("DRAGONZPYDER_MCP_TRUSTED_HOSTS", "").split(",")
                      if x.strip()}
    if not (parsed.scheme == "https" and parsed.hostname in approved_hosts
            and parsed.port in (None, 443)
            and parsed.path and parsed.path != "/" and not parsed.username
            and not parsed.password and not parsed.query and not parsed.fragment):
        raise CapabilityHubError("MCP URL requires exact, reviewed HTTPS host")
    try:
        ipaddress.ip_address(parsed.hostname or "")
    except ValueError:
        pass
    else:
        raise CapabilityHubError("IP-address MCP endpoints are not allowed")
    if (not manifest.allowed_readonly_tools or
            len(manifest.allowed_readonly_tools) > 20 or
            any(not _TOOL.fullmatch(t) or not t.startswith(manifest.name + "_")
                for t in manifest.allowed_readonly_tools)):
        raise CapabilityHubError("MCP tool names must be reviewed and server-prefixed")


async def bind_reviewed_remote_mcp(hub: CapabilityHub, manifests: list[ApprovedMCPServer]):
    """Bind only specifically reviewed read-only endpoints to the current run.

    Capability annotations supplied by third-party servers are not trusted.
    The operator must validate each permitted tool's actual side effects.
    Never use this method to connect private OAuth accounts until user-scoped
    authorization, refresh and revocation handling are implemented.
    """
    if (os.getenv("DRAGONZPYDER_MCP_EXPERIMENTAL_ENABLED") != "1" or
            os.getenv("DRAGONZPYDER_MCP_EGRESS_FIREWALL_ENFORCED") != "1"):
        raise CapabilityHubError("MCP adapter is disabled until egress isolation is proven")
    if not 1 <= len(manifests) <= 3:
        raise CapabilityHubError("Unsupported MCP server count")
    for manifest in manifests:
        _require_reviewed_server(manifest)
    if len({m.name for m in manifests}) != len(manifests):
        raise CapabilityHubError("Duplicate MCP server names")
    # Keep the previous manifest shape as a compatibility boundary. It stores
    # aliases prefixed with the server name; the original tool name is the
    # suffix. All discovery now passes through the provider-neutral broker.
    grants = []
    for manifest in manifests:
        prefix = manifest.name + "_"
        grants.append(McpGrant(
            manifest.name, manifest.url,
            frozenset({urlsplit(manifest.url).hostname}), {},
            frozenset(name[len(prefix):] for name in manifest.allowed_readonly_tools),
        ))
    try:
        selected = await asyncio.wait_for(
            discover_granted_mcp_tools(grants, max_tools=40), timeout=12,
        )
    except Exception as exc:
        raise CapabilityHubError("Approved MCP tools could not be verified") from exc
    allowed = {name for manifest in manifests for name in manifest.allowed_readonly_tools}
    if {tool.name for tool in selected} != allowed:
        raise CapabilityHubError("Approved MCP tools could not be verified")
    hub.register(provider="mcp", tools=selected, risk="approved")
    return hub


def reviewed_public_catalog_tools() -> list:
    """Optional operator-curated PUBLIC read-only MCP catalog for Personal chat.

    One static registry manifest works with any compliant Streamable HTTP
    MCP server. No user secrets, URLs, credentials, or write grants come from
    model input. Private OAuth connections need an explicit issuer integration.
    Do not enable until an enforcing egress firewall has been verified.
    """
    if os.getenv("DRAGONZPYDER_MCP_PERSONAL_PUBLIC_CATALOG_ENABLED") != "1":
        return []
    if (os.getenv("DRAGONZPYDER_MCP_EXPERIMENTAL_ENABLED") != "1"
            or os.getenv("DRAGONZPYDER_MCP_EGRESS_FIREWALL_ENFORCED") != "1"):
        raise CapabilityHubError("Reviewed MCP catalog requires enforced egress")
    hosts = frozenset(x.strip().lower() for x in
        os.getenv("DRAGONZPYDER_MCP_TRUSTED_HOSTS", "").split(",") if x.strip())
    raw = os.getenv("DRAGONZPYDER_MCP_PUBLIC_CATALOG_JSON", "[]")
    if len(raw.encode("utf-8")) > 500000:
        raise CapabilityHubError("MCP catalog manifest exceeds bound")
    try:
        rows = json.loads(raw)
        if not isinstance(rows, list) or not 1 <= len(rows) <= 1000:
            raise ValueError("Invalid catalog size")
        entries = []
        for row in rows:
            if not isinstance(row, dict) or set(row) - {
                "provider_id", "url", "readonly_tools", "description",
            }:
                raise ValueError("Invalid manifest fields")
            provider = row["provider_id"]
            url = row["url"]
            names = row["readonly_tools"]
            description = row.get("description", "")
            if (not isinstance(provider, str) or provider == "operly"
                    or not isinstance(url, str)
                    or not isinstance(names, list)
                    or not 1 <= len(names) <= 40
                    or not all(isinstance(name, str) for name in names)
                    or len(set(names)) != len(names)
                    or not isinstance(description, str)
                    or len(description) > 500):
                raise ValueError("Bad MCP manifest")
            parsed = urlsplit(url)
            if (parsed.scheme != "https" or not parsed.hostname
                    or parsed.hostname not in hosts):
                raise ValueError("Unreviewed MCP endpoint")
            try:
                ipaddress.ip_address(parsed.hostname)
            except ValueError:
                pass
            else:
                raise ValueError("IP-address endpoint forbidden")
            if parsed.hostname == "localhost" or "." not in parsed.hostname:
                raise ValueError("Local endpoint forbidden")
            exact_names = frozenset(names)
            entries.append(CatalogGrant(
                McpGrant(provider, url, hosts, {}, exact_names),
                exact_names, description,
            ))
        return catalog_tools(McpRunCatalog(entries))
    except (KeyError, ValueError, TypeError) as exc:
        raise CapabilityHubError("Invalid reviewed MCP catalog configuration") from exc
