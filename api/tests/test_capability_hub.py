"""Per-run capability registration guard: no dynamic tool escalation."""
from types import SimpleNamespace
import pytest

from agent_platform.capability_hub import (
    CapabilityHub, CapabilityHubError, operly_personal_or_workspace_hub,
)


async def empty(_):
    return {}


def fake(name):
    return SimpleNamespace(name=name, ainvoke=empty)


def test_bindings_have_provider_and_risk_without_leaking_secrets():
    hub = CapabilityHub(max_tools=3)
    hub.register(provider="native", risk="local", tools=[fake("read_file")])
    hub.register(provider="operly", risk="read_only", tools=[fake("business_status")])
    assert [r["name"] for r in hub.catalog()] == ["read_file", "business_status"]
    assert [r["risk"] for r in hub.catalog()] == ["local", "read_only"]
    assert [t.name for t in hub.tools()] == ["read_file", "business_status"]


def test_duplicate_name_cannot_override_a_registered_tool():
    hub = CapabilityHub()
    hub.register(provider="native", risk="local", tools=[fake("read_file")])
    with pytest.raises(CapabilityHubError):
        hub.register(provider="mcp", risk="approved", tools=[fake("read_file")])
    assert len(hub.tools()) == 1


@pytest.mark.parametrize("provider,risk,tool", [
    ("unknown/evil", "read_only", fake("safe_tool")),
    ("operly", "unreviewed", fake("safe_tool")),
    ("operly", "read_only", fake("../escape")),
    ("operly", "read_only", "not-a-langchain-tool"),
])
def test_invalid_capability_binding_is_rejected(provider, risk, tool):
    with pytest.raises(CapabilityHubError):
        CapabilityHub().register(provider=provider, risk=risk, tools=[tool])


def test_hub_never_grants_operly_access_without_a_real_delegation(monkeypatch):
    def refuse(_):
        raise RuntimeError("lease invalid")
    monkeypatch.setattr("agent_platform.operly_broker.readonly_tools", refuse)
    with pytest.raises(RuntimeError, match="lease invalid"):
        operly_personal_or_workspace_hub("untrusted")
