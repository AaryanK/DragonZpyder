"""Offline, zero-inference local capability and Hatchet contracts."""
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
from pydantic import ValidationError
from agent_platform.local_tools import LocalToolRegistry, LocalToolError
from agent_platform.local_monitor import (
    LocalMonitorInput, MonitorPolicy, _bucket, decide, make_local_monitor_task,
    install_staging_monitor_cron, require_monitor_gate, sample_local_tools,
)


class StubTools:
    def __init__(self, memory=31.0, disk=48.0):
        self.calls = []
        self.memory, self.disk = memory, disk

    def invoke(self, name, arguments=None):
        self.calls.append((name, arguments))
        if name == "time.now":
            return {"utc": "2026-11-19T08:00:00+00:00", "unix_seconds": 1795075200}
        if name == "system.memory":
            return {"used_percent": self.memory, "scope": "container"}
        if name == "system.disk":
            return {"used_percent": self.disk, "scope": "worker_root"}
        raise AssertionError("Unexpected tool")


def test_read_only_local_tools_reject_arbitrary_commands_and_paths():
    tools = LocalToolRegistry()
    catalog = tools.catalog()
    assert [x["name"] for x in catalog] == ["time.now", "system.memory", "system.disk"]
    assert all(x["risk"] == "read_only" and x["inputSchema"]["additionalProperties"] is False for x in catalog)
    assert tools.invoke("time.now")["utc"].endswith("+00:00")
    assert 0 <= tools.invoke("system.memory")["used_percent"] <= 100
    assert 0 <= tools.invoke("system.disk")["used_percent"] <= 100
    for name, args in [("system.shell", {}), ("system.disk", {"path": "/etc"}),
                       ("system.memory", "string"), ("../secrets", {})]:
        with pytest.raises(LocalToolError):
            tools.invoke(name, args)


def test_agent_uses_all_three_local_tools_and_decides_from_history():
    tools = StubTools(memory=88.0, disk=94.0)
    observation = sample_local_tools(tools)
    assert [name for name, _ in tools.calls] == ["time.now", "system.memory", "system.disk"]
    assert decide(observation, MonitorPolicy(), {"memory": {"used_percent": 45.0}}) == {
        "status": "attention", "alerts": ["ram_high", "disk_high", "ram_jump"]
    }
    assert decide(sample_local_tools(StubTools()), MonitorPolicy(), None)["status"] == "healthy"


def test_bucket_and_policy_checks():
    now = datetime(2026, 11, 19, 8, 8, 21, tzinfo=timezone.utc)
    assert _bucket(now, 5) == datetime(2026, 11, 19, 8, 5, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        _bucket(now.replace(tzinfo=None), 5)
    with pytest.raises(ValueError):
        MonitorPolicy(interval_minutes=7)
    with pytest.raises(ValueError):
        MonitorPolicy(memory_warn_percent=101)
    with pytest.raises(ValidationError):
        LocalMonitorInput(monitor_key="../other-user")


def test_monitor_is_disabled_by_default_and_in_production(monkeypatch):
    monkeypatch.delenv("DRAGONZPYDER_LOCAL_MONITOR_ENABLED", raising=False)
    with pytest.raises(RuntimeError, match="disabled"):
        require_monitor_gate()
    monkeypatch.setenv("DRAGONZPYDER_LOCAL_MONITOR_ENABLED", "1")
    monkeypatch.setenv("DRAGONZPYDER_STAGE", "production")
    with pytest.raises(RuntimeError, match="disabled"):
        require_monitor_gate()
    monkeypatch.setenv("DRAGONZPYDER_STAGE", "staging")
    with pytest.raises(RuntimeError, match="PostgreSQL"):
        require_monitor_gate()


class FakeHatchet:
    def __init__(self):
        self.config = None

    def task(self, **kwargs):
        self.config = kwargs
        return lambda fn: fn


class FakeCron:
    def __init__(self):
        self.calls = []

    async def aio_create_cron(self, **kwargs):
        self.calls.append(kwargs)
        return {"ok": True}


def test_task_registration_without_cron_or_model():
    fake = FakeHatchet()
    assert callable(make_local_monitor_task(fake))
    assert fake.config["name"] == "dragonzpyder-local-health-v1"
    assert fake.config["concurrency"] == 1
    assert fake.config["retries"] == 1


def test_operator_only_cron_schedule(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_LOCAL_MONITOR_ENABLED", "1")
    monkeypatch.setenv("DRAGONZPYDER_STAGE", "staging")
    monkeypatch.setenv("DRAGONZPYDER_LOCAL_MONITOR_DATABASE_URL", "postgresql://db/test")
    cron = FakeCron()
    with pytest.raises(RuntimeError, match="Operator approval"):
        asyncio.run(install_staging_monitor_cron(cron))
    monkeypatch.setenv("DRAGONZPYDER_LOCAL_MONITOR_CRON_INSTALL_ALLOWED", "1")
    asyncio.run(install_staging_monitor_cron(cron, policy=MonitorPolicy(interval_minutes=5)))
    assert cron.calls[0]["expression"] == "*/5 * * * *"
    assert cron.calls[0]["input"].monitor_key == "worker-health"
    asyncio.run(install_staging_monitor_cron(cron, policy=MonitorPolicy(interval_minutes=60)))
    assert cron.calls[1]["expression"] == "0 * * * *"
