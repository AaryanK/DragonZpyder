"""Deterministic, zero-inference benchmark acceptance: no real time waiting."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_platform.ops_benchmark import benchmark, scenarios, simulate, STRATEGIES


def test_virtual_time_covers_three_scenarios_and_exhausts_five_days():
    cases = scenarios()
    assert {x.name for x in cases} == {
        "high_frequency_stream", "hourly_web_watch", "five_day_research",
    }
    assert cases[-1].duration_s == 5 * 24 * 3600
    assert len(STRATEGIES) == 3


def test_high_frequency_push_fallback_preserves_more_updates():
    stream = scenarios()[0]
    naive = simulate(stream, "periodic_full_agent")
    poll = simulate(stream, "stateful_conditional_poll")
    hybrid = simulate(stream, "event_first_with_poll_fallback")
    assert naive["recall_pct"] < 70
    assert hybrid["recall_pct"] >= 99
    assert hybrid["delivered"] > poll["delivered"]
    # Coalescing should greatly reduce model wakeups versus event-by-event.
    assert hybrid["model_invocations"] < 50
    assert hybrid["duplicate_publications"] == 0
    assert hybrid["worker_restarts"] == 1
    assert hybrid["delivery_retries"] > 0


def test_sparse_hourly_monitor_uses_model_only_when_changed():
    watch = scenarios()[1]
    naive = simulate(watch, "periodic_full_agent")
    optimized = simulate(watch, "stateful_conditional_poll")
    assert naive["model_invocations"] > 100
    assert optimized["model_invocations"] == 5
    assert optimized["conditional_304"] > 100
    assert optimized["source_bytes"] < naive["source_bytes"]
    assert optimized["recall_pct"] == 100
    assert optimized["http_failures"] >= 1


def test_five_day_research_has_no_double_publish_and_fewer_model_calls():
    research = scenarios()[2]
    raw = simulate(research, "periodic_full_agent")
    hybrid = simulate(research, "event_first_with_poll_fallback")
    assert hybrid["virtual_duration_h"] == 120
    assert hybrid["recall_pct"] == 100
    assert hybrid["model_invocations"] < raw["model_invocations"] / 3
    assert hybrid["duplicate_publications"] == 0
    assert hybrid["worker_restarts"] == 1
    assert hybrid["latency_p95_s"] < raw["latency_p95_s"]


def test_benchmark_report_is_deterministic_except_wall_time():
    from json import dumps
    first = benchmark()
    second = benchmark()
    first.pop("wall_elapsed_ms")
    second.pop("wall_elapsed_ms")
    assert dumps(first, sort_keys=True) == dumps(second, sort_keys=True)
    assert first["kind"].startswith("deterministic_virtual_time")
    assert len(first["summary"]) == 9
