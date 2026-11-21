"""Current-turn isolation for paused Personal runs under quota pressure."""
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_platform.personal_bridge import checkpoint_advanced_for_prompt
from agent_platform.runtime import summarize_checkpoint_evidence


def snap(*messages):
    return SimpleNamespace(values={"messages": list(messages)})


def message(kind, content="", *, name="", status="success"):
    return SimpleNamespace(type=kind, content=content, name=name, status=status)


def test_new_user_turn_is_persisted_before_reporting_quota_pause():
    prior = snap(message("human", "older"), message("tool", name="operly_tasks_list"))
    after = snap(*prior.values["messages"], message("human", "new objective"))
    assert checkpoint_advanced_for_prompt(prior, after, "new objective")
    assert not checkpoint_advanced_for_prompt(prior, after, "different objective")


def test_no_new_checkpoint_is_not_represented_as_paused_execution():
    prior = snap(message("human", "older"))
    assert not checkpoint_advanced_for_prompt(prior, prior, "older")
    assert not checkpoint_advanced_for_prompt(None, prior, "older")
    assert not checkpoint_advanced_for_prompt(prior, snap(), "older")
    assert not checkpoint_advanced_for_prompt(prior, SimpleNamespace(values={}), "older")


def test_paused_checkpoint_excludes_historical_tool_receipts():
    state = {"messages": [
        message("human", "previous objective"),
        message("tool", name="operly_tasks_list"),
        message("tool", name="write_file"),
        message("human", "new objective"),
        message("tool", name="eval"),
    ], "files": {}}
    result = summarize_checkpoint_evidence(state, termination_reason="inference_limit_reached")
    assert result["status"] == "incomplete"
    assert result["termination_reason"] == "inference_limit_reached"
    assert result["successful_tools"] == ["eval"]
    assert not result["objective_verified"]


def test_paused_checkpoint_with_no_new_tool_calls_is_not_prior_success():
    state = {"messages": [
        message("human", "previous objective"),
        message("tool", name="operly_tasks_list"),
        message("human", "new objective"),
    ], "files": {}}
    result = summarize_checkpoint_evidence(state, termination_reason="inference_limit_reached")
    assert result["successful_tools"] == []
    assert result["status"] == "incomplete"
