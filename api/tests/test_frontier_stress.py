"""Long-horizon stress suite: zero-cost truthful capability and harness checks."""
from __future__ import annotations

import asyncio
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_platform.frontier_stress import (
    load_suite, readiness_report, score_report, parallel_overlap,
    live_eval_enabled, run_live_case,
)


def test_ten_distinct_long_frontier_style_domains():
    suite = load_suite()
    assert len(suite) == 10
    assert len({c["domain"] for c in suite}) == 10
    assert sum(len(c["prompt"].split()) for c in suite) >= 5000
    assert all(len(c["tracks"]) >= 3 for c in suite)
    assert all(len(c["expected_artifacts"]) >= 3 for c in suite)


def test_readiness_is_not_a_claim_of_ten_passes():
    result = readiness_report()
    assert result["real_model_runs"] == 0
    assert result["count"] == 10
    assert result["all_cases_outcome_verified"] is False
    assert all(c["status"] == "not_executed" for c in result["cases"])
    assert all(c["objective_verified"] is False for c in result["cases"])


def test_parallelism_requires_two_measured_overlapping_distinct_agents():
    assert not parallel_overlap(None)
    assert not parallel_overlap([{"agent": "analyst", "start_ms": 0, "end_ms": 100}])
    assert not parallel_overlap([
        {"agent": "analyst", "start_ms": 0, "end_ms": 100},
        {"agent": "reviewer", "start_ms": 100, "end_ms": 180},
    ])
    assert not parallel_overlap([
        {"agent": "analyst", "start_ms": 0, "end_ms": 100},
        {"agent": "analyst", "start_ms": 30, "end_ms": 80},
    ])
    assert parallel_overlap([
        {"agent": "analyst", "start_ms": 0, "end_ms": 100},
        {"agent": "reviewer", "start_ms": 40, "end_ms": 110},
    ])


def test_hallucinated_artifacts_and_tool_names_do_not_pass():
    case = load_suite()[0]
    report = {
        "answer": "I wrote all files and had three parallel agents verify them.",
        "virtual_artifact_paths": [],
        "successful_tools": [],
        "objective_verified": True,
    }
    score = score_report(case, report)
    assert score["objective_verified"] is False
    assert score["artifact_files_created"] == []
    assert not score["parallelism_observed"]
    assert "sandbox" in score["missing_capabilities"]


def test_artifact_presence_and_write_read_evidence_are_only_partial():
    case = next(c for c in load_suite() if c["id"] == "F08")
    paths = ["/workspace/school/" + n for n in case["expected_artifacts"]]
    evidence = score_report(case, {
        "answer": "Files complete", "virtual_artifact_paths": paths,
        "successful_tools": ["write_file", "read_file"], "objective_verified": True,
    }, supported=set(case["required_capabilities"]), receipts=[{
        "kind": "sandbox_test", "verified": True,
    }])
    assert set(evidence["artifact_files_created"]) == set(case["expected_artifacts"])
    assert evidence["read_back_observed"]
    assert not evidence["objective_verified"]  # no overlap trace


def test_real_model_stress_never_runs_without_every_opt_in(monkeypatch):
    for name in [
        "DRAGONZPYDER_AGENT_EVAL_ALLOW_PAID",
        "DRAGONZPYDER_AGENT_USE_GATEWAY",
        "DRAGONZPYDER_AGENT_PRODUCTION_MODE",
        "DRAGONZPYDER_AGENT_HARNESS_V2",
        "DRAGONZPYDER_AGENT_STRESS_EVAL_ENABLED",
    ]:
        monkeypatch.delenv(name, raising=False)
    assert live_eval_enabled() is False
    with pytest.raises(RuntimeError, match="disabled"):
        asyncio.run(run_live_case("F08"))


def test_real_deepagent_can_accept_all_ten_long_prompts_without_provider(monkeypatch):
    """Real LangGraph compilation/invoke, but scripted fake model, NOT model QA."""
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langchain_core.messages import AIMessage
    from langgraph.checkpoint.memory import MemorySaver
    from agent_platform.harness import build_frontier_agent

    class Scripted(FakeMessagesListChatModel):
        def bind_tools(self, tools, **kwargs):
            return self

    monkeypatch.delenv("DRAGONZPYDER_AGENT_WEB_SEARCH_ENABLED", raising=False)
    model = Scripted(responses=[AIMessage(content=(
        "Insufficient tools for real-world completion. No changes made."
    ))] * 12)
    agent = build_frontier_agent(model, MemorySaver())
    async def evaluate():
        responses = []
        for case in load_suite():
            res = await agent.ainvoke(
                {"messages": [{"role": "user", "content": case["prompt"]}]},
                config={"configurable": {"thread_id": "stress-" + case["id"]}},
            )
            responses.append(res["messages"][-1].content)
        return responses
    result = asyncio.run(evaluate())
    assert len(result) == 10
    assert all("Insufficient tools" in r for r in result)


def test_artifact_basenames_in_wrong_workspace_cannot_be_credited():
    case = next(c for c in load_suite() if c["id"] == "F08")
    report = {
        "virtual_artifact_paths": ["/workspace/unrelated/" + n
                                   for n in case["expected_artifacts"]],
        "successful_tools": ["write_file", "read_file"],
        "objective_verified": True,
    }
    score = score_report(
        case, report, supported=set(case["required_capabilities"]),
        receipts=[{"kind": "sandbox_test", "verified": True}],
        spans=[
            {"agent": "teacher", "start_ms": 10, "end_ms": 110},
            {"agent": "reviewer", "start_ms": 20, "end_ms": 120},
        ],
        oracle={"case_id": "F08", "passed": True},
    )
    assert score["artifact_files_created"] == []
    assert score["objective_verified"] is False


def test_agent_self_claim_cannot_replace_independent_outcome_oracle():
    case = next(c for c in load_suite() if c["id"] == "F08")
    report = {
        "virtual_artifact_paths": [case["artifact_dir"] + "/" + n
                                   for n in case["expected_artifacts"]],
        "successful_tools": ["write_file", "read_file"],
        "objective_verified": True,
    }
    kwargs = {
        "supported": set(case["required_capabilities"]),
        "receipts": [{"kind": "sandbox_test", "verified": True}],
        "spans": [
            {"agent": "teacher", "start_ms": 10, "end_ms": 110},
            {"agent": "reviewer", "start_ms": 20, "end_ms": 120},
        ],
    }
    score = score_report(case, report, **kwargs)
    assert score["objective_verified"] is False
    assert score["model_run_success_claim"] is True
    assert score["independent_outcome_oracle_passed"] is False
    wrong_case = score_report(case, report, oracle={
        "case_id": "F07", "passed": True,
    }, **kwargs)
    assert wrong_case["objective_verified"] is False
    correct_case = score_report(case, report, oracle={
        "case_id": "F08", "passed": True,
    }, **kwargs)
    assert correct_case["objective_verified"] is True


def test_all_expected_artifacts_have_exact_paths_and_f02_numeric_tolerance_is_not_a_file():
    for case in load_suite():
        assert case["artifact_dir"].startswith("/workspace/")
        assert all(case["artifact_dir"] + "/" + name in case["prompt"]
                   for name in case["expected_artifacts"])
    f02 = next(c for c in load_suite() if c["id"] == "F02")
    assert "0.005" not in f02["expected_artifacts"]
    assert "0.005" in f02["pass_requirements"]
