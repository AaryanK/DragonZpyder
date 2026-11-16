"""Offline-only checks for DragonZpyder synthetic agent benchmarks."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_platform.evaluation import load_cases, score_case, summarize


def test_task_suite_is_broad_and_explicitly_synthetic():
    cases = load_cases()
    assert len(cases) >= 10
    assert len({case["category"] for case in cases}) >= 8
    assert all(case.get("objective") for case in cases)


def test_agent_must_not_claim_unperformed_actions():
    case = next(x for x in load_cases() if x["id"] == "action-honesty")
    passed = score_case(case, "I cannot make the booking without permission and tools")
    assert passed["smoke_passed"]
    bad = score_case(case, "I cannot assist. Flight booked and payment completed.")
    assert not bad["smoke_passed"]
    assert len(bad["forbidden_claims"]) == 2


def test_virtual_artifact_requires_tool_evidence():
    case = next(x for x in load_cases() if x["id"] == "virtual-workspace")
    answer = "I created /workspace/plan.md in the virtual workspace."
    assert not score_case(case, answer)["smoke_passed"]
    report = score_case(case, answer, tool_names=["write_file", "read_file"])
    assert report["smoke_passed"]
    assert summarize([report])["passed"] == 1



def test_paid_eval_never_runs_by_default(monkeypatch):
    import asyncio
    import pytest
    from agent_platform.eval_runner import evaluate
    for name in (
        "DRAGONZPYDER_AGENT_EVAL_ALLOW_PAID",
        "DRAGONZPYDER_AGENT_USE_GATEWAY",
        "DRAGONZPYDER_AGENT_PRODUCTION_MODE",
        "DRAGONZPYDER_AGENT_HARNESS_V2",
    ):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(RuntimeError, match="explicit gateway-only opt-in"):
        asyncio.run(evaluate(["daily-inbox"]))


def test_smoke_success_never_counts_as_verified_completion():
    case = next(x for x in load_cases() if x["id"] == "virtual-workspace")
    report = score_case(
        case,
        "I created /workspace/plan.md in the virtual workspace.",
        tool_names=["write_file", "read_file"],
    )
    assert report["smoke_passed"] is True
    assert report["verified_completion"] is False
    summary = summarize([report])
    assert summary["passed"] == 1
    assert summary["verified_completions"] == 0


def test_runner_failure_is_explicitly_not_verified(monkeypatch):
    """Offline failure injection: no provider calls or credentials."""
    import asyncio
    from agent_platform import eval_runner

    class FailingRuntime:
        async def start(self):
            pass

        async def run_report(self, **kwargs):
            raise RuntimeError("synthetic failure")

        async def close(self):
            pass

    monkeypatch.setattr(eval_runner, "evaluation_enabled", lambda: True)
    monkeypatch.setattr(eval_runner, "AgentRuntime", FailingRuntime)
    result = asyncio.run(eval_runner.evaluate(["virtual-workspace"]))
    failure = result["case_results"][0]
    assert failure["smoke_passed"] is False
    assert failure["verified_completion"] is False
    assert failure["failure_type"] == "RuntimeError"
    assert result["summary"]["verified_completions"] == 0



def test_runner_closes_runtime_after_startup_failure(monkeypatch):
    """A failed startup must not leave a partially initialized runtime open."""
    import asyncio
    import pytest
    from agent_platform import eval_runner

    events = []

    class FailingStartupRuntime:
        async def start(self):
            events.append("start")
            raise RuntimeError("synthetic startup failure")

        async def close(self):
            events.append("close")

    monkeypatch.setattr(eval_runner, "evaluation_enabled", lambda: True)
    monkeypatch.setattr(eval_runner, "AgentRuntime", FailingStartupRuntime)
    with pytest.raises(RuntimeError, match="synthetic startup failure"):
        asyncio.run(eval_runner.evaluate(["virtual-workspace"]))
    assert events == ["start", "close"]
