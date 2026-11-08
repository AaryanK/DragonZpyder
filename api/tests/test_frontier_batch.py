"""Offline budget, evidence-boundary and opt-in contracts for real stress batch."""
from decimal import Decimal
import asyncio
from agent_platform.frontier_batch import validated_budget, safe_metrics, run_frontier_batch_once, ORDER


def test_batch_covers_remaining_nine_case_ids_after_prior_f07_trial():
    assert len(ORDER) == len(set(ORDER)) == 9
    assert set(ORDER) | {"F07"} == {"F01", "F02", "F03", "F04", "F05",
                                   "F06", "F07", "F08", "F09", "F10"}


def test_provider_cap_is_upstream_nonresetting_and_strict():
    good = {"approved": True, "reason": "hard_nonresetting_key_cap_verified",
            "limit_usd": "0.50", "remaining_usd": "0.455"}
    assert validated_budget(good) == Decimal("0.455")
    for bad in ({}, {**good, "approved": False},
                {**good, "reason": "unknown"},
                {**good, "limit_usd": "0.5001"},
                {**good, "remaining_usd": "NaN"},
                {**good, "remaining_usd": "1.3"},
                {**good, "limit_usd": "-0.50"}):
        assert validated_budget(bad) is None


def test_batch_metrics_never_include_model_answer_or_tool_arguments():
    raw = {"status": "insufficient_evidence", "objective_verified": False,
           "answer": "PRIVATE_PROMPT", "tool_arguments": "PRIVATE_TOOL_ARG",
           "successful_tool_count": 5, "delegated_calls_observed": 2}
    sanitized = safe_metrics("F02", raw)
    assert sanitized["successful_tool_count"] == 5
    assert sanitized["delegated_calls_observed"] == 2
    assert "PRIVATE_PROMPT" not in str(sanitized)
    assert "PRIVATE_TOOL_ARG" not in str(sanitized)


def test_batch_is_disabled_without_opt_in(monkeypatch):
    monkeypatch.delenv("DRAGONZPYDER_STAGING_FRONTIER_BATCH_ONCE", raising=False)
    asyncio.run(run_frontier_batch_once())


def test_batch_rejects_nonprivate_gateway_before_paid_call(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_STAGING_FRONTIER_BATCH_ONCE", "1")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_GATEWAY_BASE_URL", "https://evil.example")
    monkeypatch.setattr("agent_platform.frontier_batch.live_eval_enabled", lambda: True)
    monkeypatch.setenv("DRAGONZPYDER_STAGING_FRONTIER_CANARY_ONCE", "0")
    asyncio.run(run_frontier_batch_once())
