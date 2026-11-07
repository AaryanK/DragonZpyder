"""Offline graph and telemetry acceptance. No hosted model or external tools."""
import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_send_fanout_executes_three_bounded_tracks_with_measured_overlap():
    from agent_platform.orchestration import run_parallel_tracks
    gate = asyncio.Event()
    started = []

    async def worker(track):
        started.append(track["id"])
        if len(started) == 3:
            gate.set()
        await asyncio.wait_for(gate.wait(), timeout=1)
        return {"answer": "synthetic " + track["id"],
                "virtual_artifact_paths": ["/workspace/" + track["id"] + ".md"],
                "successful_tools": ["write_file"]}

    tracks = [{"id": x, "prompt": "Review an independent synthetic track"}
              for x in ("physics", "security", "logic")]
    report = asyncio.run(run_parallel_tracks(tracks, worker))
    assert report["completed"] == 3
    assert report["failed"] == 0
    assert report["parallelism_observed"] is True
    assert report["objective_verified"] is False
    assert [x["id"] for x in report["tracks"]] == sorted(started)


def test_partial_failure_is_explicit_not_fabricated_as_success():
    from agent_platform.orchestration import run_parallel_tracks

    async def worker(track):
        if track["id"] == "bad":
            raise RuntimeError("secret-user-text-must-not-leak")
        return {"answer": "synthetic", "objective_verified": True}

    r = asyncio.run(run_parallel_tracks([
        {"id": "good", "prompt": "A"},
        {"id": "bad", "prompt": "B"},
    ], worker))
    assert r["completed"] == 1 and r["failed"] == 1
    assert r["objective_verified"] is False
    assert r["tracks"][0]["failure_type"] == "RuntimeError"
    assert "secret-user-text-must-not-leak" not in str(r)


@pytest.mark.parametrize("tracks", [
    [],
    [{"id": "A", "prompt": "x"}],
    [{"id": "A", "prompt": "x"}] * 2,
    [{"id": "A", "prompt": "x"}, {"id": "B", "prompt": "x"}, {"id": "C", "prompt": "x"},
     {"id": "D", "prompt": "x"}],
    [{"id": "A", "prompt": "x", "model": "unapproved"}, {"id": "B", "prompt": "x"}],
    [{"id": "../escape", "prompt": "x"}, {"id": "B", "prompt": "x"}],
])
def test_parallel_tracks_enforce_resource_and_tool_boundaries(tracks):
    from agent_platform.orchestration import validate_tracks
    with pytest.raises(ValueError):
        validate_tracks(tracks)


def test_langchain_delegation_trace_requires_real_overlapping_completed_calls():
    from agent_platform.delegation_trace import DelegationTrace
    ticks = iter([0, 1_000_000, 2_000_000, 3_000_000, 4_000_000])
    trace = DelegationTrace(clock=lambda: next(ticks))
    trace.on_tool_start({"name": "task"}, "DO NOT STORE", run_id="sub1")
    trace.on_tool_start({"name": "task"}, "DO NOT STORE", run_id="sub2")
    trace.on_tool_end("DO NOT STORE", run_id="sub1")
    trace.on_tool_end("DO NOT STORE", run_id="sub2")
    observed = trace.snapshot()
    assert observed["parallelism_observed"] is True
    assert observed["delegated_calls_observed"] == 2
    assert "DO NOT STORE" not in str(observed)


def test_delegation_trace_excludes_failed_and_unfinished_invocations():
    from agent_platform.delegation_trace import DelegationTrace
    ticks = iter([0, 1_000_000, 2_000_000, 3_000_000, 4_000_000])
    trace = DelegationTrace(clock=lambda: next(ticks))
    trace.on_tool_start({"name": "read_file"}, "x", run_id="noise")
    trace.on_tool_start({"name": "task"}, "x", run_id="one")
    trace.on_tool_start({"name": "task"}, "x", run_id="two")
    trace.on_tool_error(ValueError("bad"), run_id="one")
    snapshot = trace.snapshot()
    assert snapshot["unfinished_calls"] == 1
    assert snapshot["parallelism_observed"] is False
    assert snapshot["delegated_calls_observed"] == 1
    assert snapshot["spans"][0]["status"] == "failed"


def test_parallel_tracks_have_real_wall_deadlines_and_isolate_timeouts():
    from agent_platform.orchestration import run_parallel_tracks

    async def worker(track):
        if track["id"] == "slow":
            await asyncio.sleep(0.3)
        return {"answer": track["id"]}

    report = asyncio.run(run_parallel_tracks([
        {"id": "slow", "prompt": "slow synthetic track"},
        {"id": "fast", "prompt": "fast synthetic track"},
    ], worker, track_timeout_s=0.02))
    assert report["completed"] == 1
    assert report["failed"] == 1
    assert report["tracks"][-1]["status"] == "failed"
    assert report["tracks"][-1]["failure_type"] == "TimeoutError"
    assert report["objective_verified"] is False


@pytest.mark.parametrize("deadline", [0, -1, 241, float("inf"), float("nan"), True])
def test_parallel_deadlines_fail_closed(deadline):
    from agent_platform.orchestration import build_parallel_graph

    async def worker(track):
        return {"answer": "ok"}

    with pytest.raises(ValueError, match="deadline"):
        build_parallel_graph(worker, track_timeout_s=deadline)
