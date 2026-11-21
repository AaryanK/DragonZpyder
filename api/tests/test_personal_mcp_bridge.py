"""First-party Operly session boundary and durable thread isolation."""
from __future__ import annotations

import os
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_platform.personal_bridge import _authorized, personal_thread


def _env():
    return {
        "DRAGONZPYDER_PERSONAL_MCP_HARNESS_ENABLED": "1",
        "DRAGONZPYDER_AGENTS_ENABLED": "1",
        "DRAGONZPYDER_AGENT_HARNESS_V2": "1",
        "DRAGONZPYDER_OPERLY_TOOLS_ENABLED": "1",
        "DRAGONZPYDER_OPERLY_MCP_ENABLED": "1",
        "DRAGONZPYDER_AGENT_USE_GATEWAY": "1",
        "DRAGONZPYDER_AGENT_PRODUCTION_MODE": "1",
        "DRAGONZPYDER_OPERLY_PERSONAL_AGENT_TOKEN": "a" * 48,
        "DRAGONZPYDER_OPERLY_MCP_SERVICE_SECRET": "b" * 48,
    }


def test_personal_route_requires_both_independent_secrets_and_feature_flags():
    with patch.dict(os.environ, _env(), clear=False):
        assert _authorized("Bearer " + "a" * 48, "b" * 48)
        assert not _authorized("Bearer " + "a" * 48, "")
        assert not _authorized("Bearer " + "z" * 48, "b" * 48)
        os.environ["DRAGONZPYDER_PERSONAL_MCP_HARNESS_ENABLED"] = "0"
        assert not _authorized("Bearer " + "a" * 48, "b" * 48)


def test_personal_checkpoints_derive_from_owner_and_conversation():
    a = personal_thread("user-A", "conversation-x")
    b = personal_thread("user-B", "conversation-x")
    c = personal_thread("user-A", "conversation-y")
    assert len(a) == 64
    assert len({a, b, c}) == 3
    assert a == personal_thread("user-A", "conversation-x")
    assert "user-A" not in a and "conversation-x" not in a


def test_personal_route_disabled_by_default(monkeypatch):
    for k in ("DRAGONZPYDER_PERSONAL_MCP_HARNESS_ENABLED",
              "DRAGONZPYDER_OPERLY_MCP_ENABLED"):
        monkeypatch.delenv(k, raising=False)
    assert not _authorized("Bearer " + "a" * 48, "b" * 48)


def test_execution_receipts_current_turn_are_bounded_and_do_not_claim_objectives():
    from agent_platform.personal_bridge import execution_receipt_report
    report = execution_receipt_report({
        "status": "completed",
        "successful_tools": ["task", "read_file", "eval", "web_search", "operly_tasks_list",
                             "bad tool", "x" * 100],
        "failed_tool_count": 2,
        "artifact_readback_paths": ["/workspace/test.md"],
    })
    assert report["tool_names"] == ["task", "read_file", "eval", "web_search", "operly_tasks_list"]
    assert report["failed_tool_count"] == 2
    assert report["artifact_readback_count"] == 0  # Historical write must not count.
    assert report["objective_verified"] is False
    assert "test.md" not in str(report)


def test_execution_receipts_count_only_with_observed_write_and_read():
    from agent_platform.personal_bridge import execution_receipt_report
    report = execution_receipt_report({
        "status": "incomplete",
        "successful_tools": ["write_file", "read_file"],
        "failed_tool_count": 300,
        "artifact_readback_paths": ["/workspace/a.md"],
    })
    assert report["status"] == "incomplete"
    assert report["artifact_readback_count"] == 1
    assert report["failed_tool_count"] == 100


def test_inference_failure_classification_only_trusts_sdk_exception_types():
    from agent_platform.personal_bridge import inference_failure_code

    class FakeProviderError(Exception):
        __module__ = "openai._exceptions"
        def __init__(self, status_code):
            self.status_code = status_code
    assert inference_failure_code(FakeProviderError(429)) == "INFERENCE_LIMIT_REACHED"
    assert inference_failure_code(FakeProviderError(502)) == "INFERENCE_PROVIDER_UNAVAILABLE"
    assert inference_failure_code(FakeProviderError(503)) == "INFERENCE_PROVIDER_UNAVAILABLE"
    assert inference_failure_code(FakeProviderError(400)) is None

    class FakeMcpError(Exception):
        status_code = 429
    assert inference_failure_code(FakeMcpError()) is None
    wrapper = RuntimeError("safe wrapper")
    wrapper.__cause__ = FakeProviderError(429)
    assert inference_failure_code(wrapper) == "INFERENCE_LIMIT_REACHED"
