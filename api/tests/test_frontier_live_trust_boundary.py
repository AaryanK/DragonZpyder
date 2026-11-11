"""Fail-closed regression tests for the live frontier evaluation trust boundary.

These tests use no paid models, external sandbox, database, or network.
They deliberately do not assert that synthetic artifacts are verified.
"""
import asyncio

from agent_platform import frontier_stress as stress
from agent_platform import runtime as runtime_module


def test_live_case_does_not_promote_self_reported_artifacts_to_verified_success(monkeypatch):
    case = next(c for c in stress.load_suite() if c["id"] == "F08")
    paths = [case["artifact_dir"] + "/" + name for name in case["expected_artifacts"]]
    events = []

    class SyntheticRuntime:
        async def start(self):
            events.append("start")

        async def run_report(self, **kwargs):
            events.append("run")
            return {
                "execution_id": "synthetic-run",
                "status": "completed",
                "objective_verified": True,  # Untrusted agent claim.
                "virtual_artifact_paths": paths,
                "artifact_readback_paths": paths,
                "successful_tools": ["write_file", "read_file"],
                "failed_tool_count": 0,
                "delegation_spans": [
                    {"agent": "writer", "start_ms": 1, "end_ms": 100,
                     "status": "completed", "execution_id": "synthetic-run"},
                    {"agent": "reviewer", "start_ms": 2, "end_ms": 99,
                     "status": "completed", "execution_id": "synthetic-run"},
                ],
            }

        async def close(self):
            events.append("close")

    monkeypatch.setenv("DRAGONZPYDER_AGENT_STRESS_ALLOW_PARTIAL", "1")
    monkeypatch.setattr(stress, "live_eval_enabled", lambda: True)
    monkeypatch.setattr(runtime_module, "AgentRuntime", SyntheticRuntime)
    result = asyncio.run(stress.run_live_case("F08"))
    assert events == ["start", "run", "close"]
    assert result["model_run_success_claim"] is True
    assert result["artifact_files_created"] == sorted(case["expected_artifacts"])
    assert result["parallelism_observed"] is True
    assert result["independent_outcome_oracle_passed"] is False
    assert result["objective_verified"] is False
    assert result["status"] != "verified_success"


def test_live_case_never_trusts_claimed_success_without_real_readbacks(monkeypatch):
    case = next(c for c in stress.load_suite() if c["id"] == "F08")
    paths = [case["artifact_dir"] + "/" + name for name in case["expected_artifacts"]]

    class SyntheticRuntime:
        async def start(self):
            pass

        async def run_report(self, **kwargs):
            return {
                "execution_id": "synthetic-run",
                "status": "completed",
                "objective_verified": True,
                "virtual_artifact_paths": paths,
                "artifact_readback_paths": [],
                "successful_tools": ["write_file"],
                "failed_tool_count": 0,
                "delegation_spans": [],
            }

        async def close(self):
            pass

    monkeypatch.setenv("DRAGONZPYDER_AGENT_STRESS_ALLOW_PARTIAL", "1")
    monkeypatch.setattr(stress, "live_eval_enabled", lambda: True)
    monkeypatch.setattr(runtime_module, "AgentRuntime", SyntheticRuntime)
    result = asyncio.run(stress.run_live_case("F08"))
    assert result["artifact_files_read_back"] == []
    assert result["read_back_observed"] is False
    assert result["objective_verified"] is False


def test_ineligible_case_is_blocked_before_runtime_start_or_model_spend(monkeypatch):
    class MustNotStart:
        def __init__(self):
            raise AssertionError("runtime must not be constructed")

    monkeypatch.setattr(stress, "live_eval_enabled", lambda: True)
    monkeypatch.delenv("DRAGONZPYDER_AGENT_STRESS_ALLOW_PARTIAL", raising=False)
    monkeypatch.setattr(runtime_module, "AgentRuntime", MustNotStart)
    result = asyncio.run(stress.run_live_case("F08"))
    assert result["status"] == "capability_blocked"
    assert result["model_run_attempted"] is False
    assert result["objective_verified"] is False
    assert "parallel_subagents" in result["missing_capabilities"]
