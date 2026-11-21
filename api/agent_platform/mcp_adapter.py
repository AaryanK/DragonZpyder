"""Operator-reviewed remote MCP adapters for DragonZpyder's capability hub.

No user-provided endpoints, arbitrary stdio commands or auto-installation.
This is an off-by-default adapter, not a general permission to execute tools:
each server, hostname and tool name needs an independently reviewed allowlist.
An enforcing egress firewall is REQUIRED for enabled deployments.
"""
from __future__ import annotations

import asyncio
import ipaddress
import os
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from .capability_hub import CapabilityHub, CapabilityHubError

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
    from langchain_mcp_adapters.client import MultiServerMCPClient
    client = MultiServerMCPClient(
        {m.name: {"transport": "http", "url": m.url} for m in manifests},
        tool_name_prefix=True, handle_tool_errors=False,
    )
    try:
        discovered = await asyncio.wait_for(client.get_tools(), timeout=12)
    except Exception as exc:
        raise CapabilityHubError("Approved MCP discovery is unavailable") from exc
    allowed = {name for m in manifests for name in m.allowed_readonly_tools}
    selected = [tool for tool in discovered if getattr(tool, "name", "") in allowed]
    if {tool.name for tool in selected} != allowed:
        raise CapabilityHubError("Approved MCP tools could not be verified")
    hub.register(provider="mcp", tools=selected, risk="approved")
    return hub
