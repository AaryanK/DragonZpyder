"""No-paid acceptance for the real Operly MCP staging runner."""
from __future__ import annotations

from pathlib import Path
import sys

import pytest
from langchain_core.messages import ToolMessage

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_platform.live_operly_mcp_smoke import _preflight, _readback_verified


def test_real_mcp_runner_rejects_non_staging_non_private(monkeypatch):
    names = [
        "DRAGONZPYDER_AGENT_USE_GATEWAY",
        "DRAGONZPYDER_AGENT_PRODUCTION_MODE",
        "DRAGONZPYDER_AGENT_EVAL_ALLOW_PAID",
        "DRAGONZPYDER_OPERLY_TOOLS_ENABLED",
        "DRAGONZPYDER_OPERLY_MCP_ENABLED",
    ]
    for name in names:
        monkeypatch.setenv(name, "1")
    monkeypatch.setenv("DRAGONZPYDER_OPERLY_MCP_FIXTURE_AUTH", "x" * 64)
    monkeypatch.setenv("DRAGONZPYDER_HARNESS_SMOKE_DATABASE_URL",
                       "postgresql://fixture@localhost/isolated")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_GATEWAY_BASE_URL",
                       "http://dragonzpyder-gateway.railway.internal:8080/internal/agent/v1")
    monkeypatch.setenv("DRAGONZPYDER_OPERLY_MCP_FIXTURE_URL",
                       "http://operly-private-mcp-acceptance-20.railway.internal:8080/mcp")
    monkeypatch.setenv("DRAGONZPYDER_STAGE", "production")
    with pytest.raises(RuntimeError, match="not authorized"):
        _preflight()
    monkeypatch.setenv("DRAGONZPYDER_STAGE", "staging")
    url, key, _ = _preflight()
    assert url.endswith("/mcp") and len(key) == 64
    monkeypatch.setenv("DRAGONZPYDER_OPERLY_MCP_FIXTURE_URL",
                       "https://malicious.example/mcp")
    with pytest.raises(RuntimeError, match="not allowlisted"):
        _preflight()


def test_real_mcp_evidence_only_from_tool_results_not_final_model_claims():
    response = [
        ToolMessage(content='{"name":"DragonZpyder Isolated MCP Evaluation"}',
                    name="workspace.describe", tool_call_id="tool1"),
        ToolMessage(content='{"modules":[{"key":"demo","name":"Demo"}]}',
                    name="workspace.modules.list", tool_call_id="tool2"),
    ]
    yes, names = _readback_verified(response)
    assert yes and names == ["workspace.describe", "workspace.modules.list"]
    no, _ = _readback_verified(response[:1])
    assert not no
    hallucinated = [
        ToolMessage(content="Tool output contained no workspace identity",
                    name="workspace.describe", tool_call_id="tool1"),
        ToolMessage(content='{"modules":[]}',
                    name="workspace.modules.list", tool_call_id="tool2"),
    ]
    no, _ = _readback_verified(hallucinated)
    assert not no
