"""Zero-paid guard and mock-broker tests for one-shot live harness evaluation."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_platform.live_platform_tool_smoke import _gate, _synthetic_handler


def test_bounded_live_smoke_must_be_staging_and_private(monkeypatch):
    for name in (
        "DRAGONZPYDER_AGENT_USE_GATEWAY",
        "DRAGONZPYDER_AGENT_PRODUCTION_MODE",
        "DRAGONZPYDER_AGENT_EVAL_ALLOW_PAID",
        "DRAGONZPYDER_OPERLY_TOOLS_ENABLED",
    ):
        monkeypatch.setenv(name, "1")
    monkeypatch.setenv("DRAGONZPYDER_STAGE", "production")
    monkeypatch.setenv("DRAGONZPYDER_HARNESS_SMOKE_DATABASE_URL",
                       "postgresql://fixture@localhost/test")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_GATEWAY_BASE_URL",
                       "http://dragonzpyder-gateway.railway.internal:8080/internal/agent/v1")
    with pytest.raises(RuntimeError, match="disabled"):
        _gate()
    monkeypatch.setenv("DRAGONZPYDER_STAGE", "staging")
    assert _gate().startswith("postgresql://")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_GATEWAY_BASE_URL",
                       "https://untrusted.example/internal/agent/v1")
    with pytest.raises(RuntimeError, match="Unauthorized"):
        _gate()


def test_mock_broker_uses_real_operly_contract_and_refuses_writes():
    seen = []
    handler = _synthetic_handler(seen)
    headers = {
        "Authorization": "Bearer " + "t" * 48,
        "X-Operly-Agent-Lease": "synthetic-isolated-lease",
    }
    discover = handler(httpx.Request(
        "POST", "https://operly.dragonzpyder.xyz/api/internal/agent-tools/search",
        json={"query": "tasks and runtime"}, headers=headers,
    ))
    assert discover.status_code == 200
    offered = discover.json()["tools"]
    assert {x["id"] for x in offered} == {
        "tasks.list", "system.runtime.status", "tasks.create"}
    assert next(x for x in offered if x["id"] == "tasks.create")["risk"] != "read_only"

    get_tasks = handler(httpx.Request(
        "POST", "https://operly.dragonzpyder.xyz/api/internal/agent-tools/execute",
        json={"capability_id": "tasks.list", "arguments": {}}, headers=headers,
    ))
    assert get_tasks.json()["result"]["tasks"][0]["id"] == "synth-1"
    forbidden = handler(httpx.Request(
        "POST", "https://operly.dragonzpyder.xyz/api/internal/agent-tools/execute",
        json={"capability_id": "tasks.create", "arguments": {"title": "no"}},
        headers=headers,
    ))
    assert forbidden.status_code == 403
    assert len(seen) == 3
