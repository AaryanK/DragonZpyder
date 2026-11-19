"""Contract tests for real LLM-shaped tool selection (no paid inference)."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_platform.persistent_tool_canary import (
    CanaryError, GOAL_STEPS, approved_tools, bucket_of, gate, select_local_tool,
)


class FakeModel:
    def __init__(self, *, name="system_memory", args=None, calls=1):
        self.name, self.args, self.calls = name, args if args is not None else {}, calls
        self.bound_tools = []
        self.prompts = []

    def bind_tools(self, tools, tool_choice):
        assert tool_choice == "required"
        self.bound_tools = tools
        return self

    async def ainvoke(self, messages):
        self.prompts.append(messages)
        return SimpleNamespace(tool_calls=[
            {"name":self.name,"args":self.args} for _ in range(self.calls)
        ])


def test_three_read_only_schemas_and_model_selected_tool():
    model = FakeModel()
    chosen = asyncio.run(select_local_tool(model, GOAL_STEPS))
    assert chosen == "system.memory"
    assert [spec["function"]["name"] for spec in model.bound_tools] == [
        "time_now","system_memory","system_disk"
    ]
    assert all(spec["function"]["parameters"]["additionalProperties"] is False
               for spec in model.bound_tools)
    assert "password" not in str(model.prompts).lower()


@pytest.mark.parametrize("name,args,calls", [
    ("system_shell", {}, 1),
    ("workspace_finance_payment_record", {}, 1),
    ("system_memory", {"path":"/etc/passwd"}, 1),
    ("system_memory", {}, 2),
    ("system_memory", {}, 0),
])
def test_model_is_not_authorization_authority(name,args,calls):
    with pytest.raises(CanaryError):
        asyncio.run(select_local_tool(FakeModel(name=name,args=args,calls=calls),GOAL_STEPS))


def test_model_cannot_repeat_completed_tool():
    with pytest.raises(CanaryError):
        asyncio.run(select_local_tool(FakeModel(name="system_memory"),
                                      ("time.now","system.disk")))


def test_interval_boundaries():
    from datetime import datetime,timezone
    assert bucket_of(datetime(2026,11,19,9,2,tzinfo=timezone.utc)).isoformat() == "2026-11-19T09:00:00+00:00"
    assert bucket_of(datetime(2026,11,19,9,5,tzinfo=timezone.utc)).isoformat() == "2026-11-19T09:05:00+00:00"
    with pytest.raises(CanaryError):
        bucket_of(datetime(2026,11,19,9,6))


def test_staging_and_metered_gateway_required(monkeypatch):
    monkeypatch.delenv("DRAGONZPYDER_LONG_HORIZON_CANARY_ENABLED",raising=False)
    with pytest.raises(CanaryError): gate()
    monkeypatch.setenv("DRAGONZPYDER_LONG_HORIZON_CANARY_ENABLED","1")
    monkeypatch.setenv("DRAGONZPYDER_STAGE","production")
    with pytest.raises(CanaryError): gate()
    monkeypatch.setenv("DRAGONZPYDER_STAGE","staging")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_USE_GATEWAY","0")
    with pytest.raises(CanaryError): gate()
    monkeypatch.setenv("DRAGONZPYDER_AGENT_USE_GATEWAY","1")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_PRODUCTION_MODE","0")
    with pytest.raises(CanaryError): gate()
    monkeypatch.setenv("DRAGONZPYDER_AGENT_PRODUCTION_MODE","1")
    monkeypatch.setenv("DRAGONZPYDER_LONG_HORIZON_DATABASE_URL","")
    with pytest.raises(CanaryError): gate()
