"""No external services or paid inference: actual LangGraph workflow and cron tests."""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_platform.workflows.spec import (
    WorkflowSpecError, validate_workflow_spec, validate_schedule,
    next_schedule_time,
)
from agent_platform.workflows.graph import run_readonly_workflow, stable_request_id


def test_canonical_workflow_dsl_has_real_dependencies_and_guards():
    spec = validate_workflow_spec({"steps": [
        {"id": "a", "capability_id": "google.gmail.search", "arguments": {"query": "subject:invoice"}},
        {"id": "b", "capability_id": "workspace.summary.read",
         "depends_on": ["a"], "arguments": {"title": "{{ steps.a.result.title }}"}},
    ]})
    assert spec["steps"][1]["depends_on"] == ["a"]
    assert spec["steps"][0]["kind"] == "action"
    with pytest.raises(WorkflowSpecError):
        validate_workflow_spec({"steps": [{"id":"a","capability_id":"workflow.start"}]})
    with pytest.raises(WorkflowSpecError):
        validate_workflow_spec({"steps": [
            {"id":"b","capability_id":"read.one","depends_on":["a"]},
            {"id":"a","capability_id":"read.two"},
        ]})


def test_schedules_moved_to_dragonzpyder_cover_cron_and_timezone():
    cron = validate_schedule({"type": "cron", "expression":"0 9 * * 1", "timezone":"UTC"})
    assert cron["type"] == "cron"
    after = datetime(2026, 11, 9, 8, 0)
    assert next_schedule_time(cron, after=after) == datetime(2026, 11, 9, 9, 0)
    assert next_schedule_time(cron, after=datetime(2026, 11, 9, 9, 0)) == datetime(2026, 11, 16, 9, 0)
    with pytest.raises(WorkflowSpecError):
        validate_schedule({"type": "cron", "expression":"* * *", "timezone":"UTC"})
    with pytest.raises(WorkflowSpecError):
        validate_schedule({"type": "daily", "time":"09:00", "timezone":"Mars/Olympus"})


def test_langgraph_runs_two_real_steps_with_rendered_evidence():
    calls = []

    async def read(capability, args, request_id):
        calls.append((capability, args, request_id))
        return {"ok": True, "result": {"title": "Business status"}}

    spec = {"steps": [
        {"id":"first","capability_id":"operly.status","arguments":{}},
        {"id":"second","capability_id":"operly.lookup","depends_on":["first"],
         "arguments":{"term":"{{ steps.first.result.title }}"}},
    ]}
    r = asyncio.run(run_readonly_workflow(
        spec, run_id="run-test-1", allowed_capabilities=frozenset({"operly.status", "operly.lookup"}),
        executor=read,
    ))
    assert r["status"] == "completed"
    assert r["objective_verified"] is False
    assert r["action_count"] == 2
    assert r["steps"]["second"]["status"] == "completed"
    assert calls[1][1] == {"term":"Business status"}
    assert calls[0][2] == stable_request_id("run-test-1", "first")
    assert calls[0][2] != calls[1][2]


def test_langgraph_fails_closed_before_undelegated_capability_call():
    calls = []

    async def read(capability, args, request_id):
        calls.append(capability)
        return {"ok": True, "result": {}}

    r = asyncio.run(run_readonly_workflow(
        {"steps":[{"id":"a","capability_id":"workspace.members.remove","arguments":{}}]},
        run_id="run-test-2", allowed_capabilities=frozenset({"workspace.summary.read"}),
        executor=read,
    ))
    assert r["status"] == "failed"
    assert r["steps"]["a"]["error_code"] == "capability_not_delegated"
    assert calls == []


def test_graph_persists_wait_boundary_without_sleeping():
    async def no_execution(*args):
        raise AssertionError("Wait should not execute")

    r = asyncio.run(run_readonly_workflow(
        {"steps":[
            {"id":"pause","kind":"wait","seconds":60},
            {"id":"next","capability_id":"status.read","arguments":{}},
        ]}, run_id="run-test-3", allowed_capabilities=frozenset({"status.read"}),
        executor=no_execution,
    ))
    assert r["status"] == "waiting"
    assert r["waiting_step"] == "pause"
    assert r["steps"]["next"]["status"] == "blocked"
    assert r["objective_verified"] is False


def test_graph_does_not_fabricate_success_after_provider_error():
    async def read(*args):
        raise RuntimeError("provider-secret-must-not-leak")

    r = asyncio.run(run_readonly_workflow(
        {"steps":[{"id":"read","capability_id":"status.read","arguments":{}}]},
        run_id="run-test-4", allowed_capabilities=frozenset({"status.read"}),
        executor=read,
    ))
    assert r["status"] == "failed"
    assert r["steps"]["read"]["error_code"] == "execution_failed"
    assert "provider-secret-must-not-leak" not in str(r)
    assert r["objective_verified"] is False
