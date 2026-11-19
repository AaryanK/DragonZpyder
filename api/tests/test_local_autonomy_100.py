"""100 transparent local-agent fixtures for actually available tools.

These are independent deterministic scenarios, not 100 distinct MCP services.
Only five positive dispatch cases use actual worker resources; other cases
simulate fixed readings or assert a fail-closed policy. No model cost.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_platform.local_monitor import MonitorPolicy, _bucket, decide, sample_local_tools
from agent_platform.local_tools import LocalToolError, LocalToolRegistry

MANIFEST = Path(__file__).resolve().parents[1] / "agent_platform" / "benchmarks" / "local_autonomy_100.json"
SUITE = json.loads(MANIFEST.read_text(encoding="utf-8"))
CASES = SUITE["cases"]


class FixtureRegistry:
    def __init__(self, data):
        self.data = data
        self.calls = []

    def invoke(self, name, arguments=None):
        assert arguments == {}
        self.calls.append(name)
        if name == "time.now":
            return {"utc": "2026-11-19T07:00:00+00:00", "unix_seconds": 1795071600}
        if name == "system.memory":
            return {"used_percent": self.data["ram_percent"]}
        if name == "system.disk":
            return {"used_percent": self.data["disk_percent"]}
        raise AssertionError("Scenario requested an unapproved tool")


def test_manifest_is_100_unique_labeled_scenarios():
    assert SUITE["schema_version"] == "1"
    assert len(CASES) == 100
    assert len({case["id"] for case in CASES}) == 100
    assert len({case["title"] for case in CASES}) == 100
    assert {case["kind"] for case in CASES} == {
        "monitor", "schedule", "dispatch", "policy"
    }
    assert {case["execution"] for case in CASES} == {
        "offline_simulation", "live_local_read", "offline_negative_test",
        "offline_validation",
    }
    assert all(case["id"] == f"LOCAL-{i:03d}" for i, case in enumerate(CASES, 1))


@pytest.mark.parametrize("case", CASES, ids=lambda x: x["id"])
def test_one_available_local_agent_scenario(case):
    kind = case["kind"]
    if kind == "monitor":
        tools = FixtureRegistry(case)
        observation = sample_local_tools(tools)
        previous = ({"memory": {"used_percent": case["previous_ram_percent"]}}
                    if case["previous_ram_percent"] is not None else None)
        decision = decide(observation, MonitorPolicy(), previous)
        assert decision == {
            "status": case["expected_status"], "alerts": case["expected_alerts"]
        }
        assert tools.calls == ["time.now", "system.memory", "system.disk"]
        return
    if kind == "schedule":
        moment = datetime.fromisoformat(case["at"])
        assert _bucket(moment, case["interval_minutes"]).isoformat() == case["expected_bucket"]
        return
    if kind == "dispatch":
        tools = LocalToolRegistry()
        if case["expected"] == "deny":
            with pytest.raises(LocalToolError):
                tools.invoke(case["name"], case["arguments"])
        else:
            result = tools.invoke(case["name"], case["arguments"])
            assert isinstance(result, dict) and result
            if case["name"] == "time.now":
                assert datetime.fromisoformat(result["utc"]).tzinfo is not None
            else:
                assert 0 <= result["used_percent"] <= 100
        return
    if kind == "policy":
        if case["expected"] == "deny":
            with pytest.raises((ValueError, TypeError)):
                MonitorPolicy(**case["arguments"])
        else:
            assert isinstance(MonitorPolicy(**case["arguments"]), MonitorPolicy)
        return
    raise AssertionError(f"Unknown executable scenario kind {kind}")
