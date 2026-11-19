"""DragonZpyder-owned capability hub for a single authorized agent run.

The hub owns *tool discovery and binding* for the LangGraph harness.
Operly is a remote provider of business/workspace capabilities, never a
second agent runtime. Future MCP adapters register through the same interface.

Do not cache a hub across user runs: tools hold delegated, expiring authority.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

_NAME = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{0,79}$")
_PROVIDER = re.compile(r"^[a-z][a-z0-9_-]{0,39}$")


class CapabilityHubError(RuntimeError):
    pass


@dataclass(frozen=True)
class ToolBinding:
    name: str
    provider: str
    risk: str  # Operly read-only, MCP operator reviewed, or local.
    tool: Any


class CapabilityHub:
    """Ephemeral, auditable binding catalogue; not an authorization server."""

    def __init__(self, *, max_tools: int = 40) -> None:
        if not 1 <= max_tools <= 100:
            raise ValueError("Invalid tool capacity")
        self._max_tools = max_tools
        self._bindings: dict[str, ToolBinding] = {}

    def register(self, *, provider: str, tools: Iterable, risk: str) -> None:
        if not _PROVIDER.fullmatch(provider):
            raise CapabilityHubError("Invalid capability provider")
        if risk not in {"read_only", "approved", "local"}:
            raise CapabilityHubError("Unclassified tool risk")
        pending = list(tools)
        if len(pending) + len(self._bindings) > self._max_tools:
            raise CapabilityHubError("Capability tool budget exceeded")
        names = [getattr(tool, "name", None) for tool in pending]
        if any(not isinstance(name, str) or not _NAME.fullmatch(name) for name in names):
            raise CapabilityHubError("Invalid tool name")
        if len(set(names)) != len(names) or any(name in self._bindings for name in names):
            raise CapabilityHubError("Duplicate or conflicting capability names")
        if any(not callable(getattr(tool, "ainvoke", None)) for tool in pending):
            raise CapabilityHubError("Tool must support asynchronous invocation")
        for name, tool in zip(names, pending):
            self._bindings[name] = ToolBinding(name, provider, risk, tool)

    def tools(self) -> list:
        # Public-to-LLM tools never carry this hub's provider credentials as
        # metadata, and a user cannot add/register tools from a chat prompt.
        return [binding.tool for binding in self._bindings.values()]

    def catalog(self) -> list[dict[str, str]]:
        return [{"name": binding.name, "provider": binding.provider,
                 "risk": binding.risk} for binding in self._bindings.values()]


def operly_personal_or_workspace_hub(lease: str) -> CapabilityHub:
    from .operly_broker import readonly_tools
    hub = CapabilityHub()
    hub.register(provider="operly", tools=readonly_tools(lease), risk="read_only")
    return hub
