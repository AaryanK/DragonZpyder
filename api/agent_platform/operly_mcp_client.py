"""Opt-in native MCP client for DragonZpyder -> Operly.

Use the upstream LangChain MCP adapter rather than maintaining an MCP
transport. A caller must obtain an independently authorized OAuth access token
and a trusted allowlist from its execution context. No global shared credentials,
automatic refresh, or user-identity inference occurs in this module.
"""
from __future__ import annotations

import os
import re
from urllib.parse import urlsplit

_TOOL = re.compile(r"^[a-z][a-z0-9_.:-]{1,159}$")


def _validated_url(url: str) -> str:
    parsed = urlsplit(str(url or ""))
    expected = os.getenv(
        "DRAGONZPYDER_OPERLY_MCP_HOST", "operly.dragonzpyder.xyz"
    ).strip().lower()
    is_public = (parsed.scheme == "https" and
                 parsed.hostname == expected and parsed.port in (None, 443))
    is_staging_private = (
        os.getenv("DRAGONZPYDER_STAGE") == "staging" and
        parsed.scheme == "http" and bool(parsed.hostname) and
        parsed.hostname.endswith(".railway.internal") and
        parsed.port in (None, 8080)
    )
    if (not (is_public or is_staging_private)
            or parsed.path != "/mcp" or parsed.username or parsed.password
            or parsed.query or parsed.fragment):
        raise ValueError("Operly MCP endpoint is not allowlisted")
    return url


async def load_authorized_operly_mcp_tools(*, url: str, access_token: str,
                                            approved_tool_names: frozenset[str],
                                            max_tools: int = 20,
                                            service_proof: str | None = None) -> list:
    """Load only current-run, explicitly authorized Operly MCP tools.

    The workspace-scoped OAuth token itself MUST be obtained outside the model
    and renewed between durable wakes. Never save it into LangGraph state.
    """
    if os.getenv("DRAGONZPYDER_OPERLY_MCP_ENABLED") != "1":
        raise RuntimeError("Native Operly MCP client not enabled")
    endpoint = _validated_url(url)
    if (not isinstance(access_token, str) or not 32 <= len(access_token) <= 8192
            or not isinstance(approved_tool_names, frozenset)
            or not 1 <= len(approved_tool_names) <= 40
            or any(not isinstance(s, str) or not _TOOL.fullmatch(s)
                   for s in approved_tool_names)
            or not 1 <= max_tools <= 20):
        raise ValueError("Invalid scoped MCP tool delegation")

    if service_proof is not None and (
        not isinstance(service_proof, str) or len(service_proof) < 40
    ):
        raise ValueError("Invalid first-party Operly service authority")
    # Operly owns user authorization. The provider-neutral broker owns MCP
    # transport, schema adaptation, namespacing, and tool discovery.
    from .mcp_broker import McpGrant, discover_granted_mcp_tools

    return await discover_granted_mcp_tools(
        [
            McpGrant(
                provider_id="operly",
                url=endpoint,
                allowed_hosts=frozenset({
                    os.getenv("DRAGONZPYDER_OPERLY_MCP_HOST", "operly.dragonzpyder.xyz")
                    .strip().lower(),
                    *(("operly.railway.internal",)
                      if os.getenv("DRAGONZPYDER_STAGE") == "staging" else ()),
                }),
                headers={
                    "Authorization": "Bearer " + access_token,
                    **({"X-Operly-Agent-Service": service_proof}
                       if service_proof is not None else {}),
                },
                capability_ids=approved_tool_names,
            )
        ], max_tools=max_tools,
    )
