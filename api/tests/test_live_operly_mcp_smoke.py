"""No-paid acceptance for the real Operly MCP staging runner."""
from __future__ import annotations

from pathlib import Path
import sys

import pytest
from langchain_core.messages import ToolMessage, AIMessage

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_platform.live_operly_mcp_smoke import _preflight, _readback_verified, _has_terminal_ai_answer


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
                    name="operly_workspace_describe", tool_call_id="tool1"),
        ToolMessage(content='{"modules":[{"key":"demo","name":"Demo"}]}',
                    name="operly_workspace_modules_list", tool_call_id="tool2"),
    ]
    yes, names = _readback_verified(response)
    assert yes and names == ["operly_workspace_describe", "operly_workspace_modules_list"]
    no, _ = _readback_verified(response[:1])
    assert not no
    hallucinated = [
        ToolMessage(content="Tool output contained no workspace identity",
                    name="operly_workspace_describe", tool_call_id="tool1"),
        ToolMessage(content='{"modules":[]}',
                    name="operly_workspace_modules_list", tool_call_id="tool2"),
    ]
    no, _ = _readback_verified(hallucinated)
    assert not no


@pytest.mark.parametrize("messages,expected", [
    ([], False),
    ([ToolMessage(content="ok", name="operly_workspace_describe", tool_call_id="t")], False),
    ([AIMessage(content="")], False),
    ([AIMessage(content="   ")], False),
    ([AIMessage(content="calling", tool_calls=[{"name": "operly_workspace_describe", "args": {}, "id": "t"}])], False),
    ([AIMessage(content="Observed workspace and modules.")], True),
])
def test_real_mcp_requires_terminal_answer(messages, expected):
    assert _has_terminal_ai_answer(messages) is expected


@pytest.mark.parametrize("bad_content,tool_name", [
    ('{"error":"DragonZpyder Isolated MCP Evaluation"}', "operly_workspace_describe"),
    ('{"name":"wrong","message":"DragonZpyder Isolated MCP Evaluation"}', "operly_workspace_describe"),
    ('{"note":"\\\"modules\\\" mentioned but not returned"}', "operly_workspace_modules_list"),
    ('{"modules":"not-a-list"}', "operly_workspace_modules_list"),
    ('{"modules":[{"key":"","name":"Demo"}]}', "operly_workspace_modules_list"),
    ('not-json', "operly_workspace_describe"),
])
def test_real_mcp_rejects_malformed_receipts(bad_content, tool_name):
    messages = [
        ToolMessage(content='{"name":"DragonZpyder Isolated MCP Evaluation"}',
                    name="operly_workspace_describe", tool_call_id="one"),
        ToolMessage(content='{"modules":[{"key":"demo","name":"Demo"}]}',
                    name="operly_workspace_modules_list", tool_call_id="two"),
    ]
    index = 0 if tool_name == "operly_workspace_describe" else 1
    messages[index] = ToolMessage(content=bad_content, name=tool_name,
                                  tool_call_id="bad")
    verified, _ = _readback_verified(messages)
    assert not verified


def test_real_mcp_rejects_duplicate_and_failed_receipts():
    valid = [
        ToolMessage(content='{"name":"DragonZpyder Isolated MCP Evaluation"}',
                    name="operly_workspace_describe", tool_call_id="one"),
        ToolMessage(content='{"modules":[]}', name="operly_workspace_modules_list",
                    tool_call_id="two"),
    ]
    assert _readback_verified(valid)[0]
    assert not _readback_verified([valid[0], valid[0], valid[1]])[0]
    failed = ToolMessage(content=valid[0].content, name=valid[0].name,
                         tool_call_id="failed", status="error")
    assert not _readback_verified([failed, valid[1]])[0]
