"""Hatchet cron and synthetic worker wiring: API contracts without inference."""
from __future__ import annotations

import asyncio
from datetime import timedelta
from types import SimpleNamespace

import pytest

from agent_platform.goal_tick import (
    GoalTickInput, install_staging_goal_cron,
    make_goal_tick_task, require_synthetic_gate,
)
from agent_platform.goal_tick_admin import _operator_guard


def enable(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_GOAL_STORE_ENABLED", "1")
    monkeypatch.setenv("DRAGONZPYDER_GOAL_TICK_ENABLED", "1")
    monkeypatch.setenv("DRAGONZPYDER_GOAL_SYNTHETIC_ONLY", "1")
    monkeypatch.setenv("DRAGONZPYDER_GOALS_DATABASE_URL", "postgresql://db.example/test")
    monkeypatch.setenv("DRAGONZPYDER_STAGE", "staging")
    monkeypatch.setenv("DRAGONZPYDER_GOAL_CRON_INSTALL_ALLOWED", "1")


class FakeHatchet:
    def __init__(self):
        self.config = {}

    def task(self, **kwargs):
        self.config = kwargs
        return lambda fn: fn


class FakeTask:
    def __init__(self):
        self.calls = []

    async def aio_create_cron(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(metadata=SimpleNamespace(id="synthetic-cron"))


def test_goal_worker_is_off_by_default(monkeypatch):
    monkeypatch.delenv("DRAGONZPYDER_GOAL_TICK_ENABLED", raising=False)
    with pytest.raises(RuntimeError, match="disabled"):
        require_synthetic_gate()


def test_goal_worker_registration_does_not_install_cron(monkeypatch):
    enable(monkeypatch)
    fake = FakeHatchet()
    handler = make_goal_tick_task(fake)
    assert callable(handler)
    assert fake.config["name"] == "dragonzpyder-goal-reconcile-v1"
    assert fake.config["retries"] == 1
    assert fake.config["concurrency"] == 1
    assert fake.config["execution_timeout"] == timedelta(seconds=45)
    assert fake.config["input_validator"] is GoalTickInput


def test_explicit_cron_is_single_named_hatchet_task(monkeypatch):
    enable(monkeypatch)
    fake = FakeTask()
    asyncio.run(install_staging_goal_cron(fake))
    assert len(fake.calls) == 1
    assert fake.calls[0]["cron_name"] == "dragonzpyder-staging-goal-reconcile-v1"
    assert fake.calls[0]["expression"] == "* * * * *"
    assert fake.calls[0]["input"].mode == "reconcile"


def test_cron_provision_denied_without_operator_or_in_production(monkeypatch):
    enable(monkeypatch)
    monkeypatch.setenv("DRAGONZPYDER_STAGE", "production")
    with pytest.raises(RuntimeError, match="staging"):
        asyncio.run(install_staging_goal_cron(FakeTask()))
    monkeypatch.setenv("DRAGONZPYDER_STAGE", "staging")
    monkeypatch.delenv("DRAGONZPYDER_GOAL_CRON_INSTALL_ALLOWED", raising=False)
    with pytest.raises(RuntimeError, match="operator"):
        asyncio.run(install_staging_goal_cron(FakeTask()))


def test_only_two_explicit_admin_operations_allowed(monkeypatch):
    enable(monkeypatch)
    with pytest.raises(ValueError):
        _operator_guard("run-user-goal")
    _operator_guard("install-cron")
    _operator_guard("seed-probe")
