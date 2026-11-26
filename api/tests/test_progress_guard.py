"""Regression checks for loop termination and checkpoint evidence.

No OpenRouter key, hosted LLM, external network, filesystem or Railway is used.
"""
from __future__ import annotations

from langchain_core.messages import AIMessage, ToolMessage
from agent_platform.progress_guard import (
    MAX_STRESS_TURNS, STOP_PREFIX, action_fingerprints,
    progress_guard_decision, repeated_action_cycle, stop_reason,
)
from agent_platform.runtime import (
    controlled_termination_reason, summarize_agent_result,
    summarize_checkpoint_evidence,
)


def _model_tool(tool: str, args: dict, index: int):
    return AIMessage(content="", tool_calls=[{
        "id": "run-" + str(index), "name": tool, "args": args
    }])


def test_repeat_guard_requires_full_cycle_not_single_duplicate():
    pair = [_model_tool("read_file", {"file_path": "/workspace/a.md"}, i)
            for i in range(4)]
    assert stop_reason(pair[:3], stress_mode=False) is None
    assert stop_reason(pair, stress_mode=False) == "repeated_tool_cycle"
    assert repeated_action_cycle(action_fingerprints(pair))
    # Distinct edits are work, not a repeated identical tool action.
    edits = [_model_tool("write_file", {
        "file_path": "/workspace/a.md", "content": str(i)}, i)
        for i in range(6)]
    assert stop_reason(edits, stress_mode=True) is None


def test_stress_step_budget_returns_explicit_unverified_stopping_message(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_AGENT_STRESS_EVAL_ENABLED", "1")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_EVAL_ALLOW_PAID", "1")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_USE_GATEWAY", "1")
    state = {"messages": [AIMessage(content="step") for _ in range(MAX_STRESS_TURNS)]}
    decision = progress_guard_decision(state)
    assert decision["jump_to"] == "end"
    assert decision["messages"][0].content.startswith(STOP_PREFIX)
    report = summarize_agent_result({"messages": [*state["messages"], *decision["messages"]]})
    assert report["status"] == "incomplete"
    assert report["objective_verified"] is False
    assert report["termination_reason"] == "step_budget_exhausted"


def test_checkpoint_recovery_counts_receipts_without_assuming_success():
    a = "/workspace/verified.md"
    msgs = [
        AIMessage(content="", tool_calls=[{
            "id": "tc-write", "name": "write_file",
            "args": {"file_path": a, "content": "irrelevant test content"}
        }]),
        ToolMessage(content="File written", name="write_file",
                    tool_call_id="tc-write", status="success"),
        AIMessage(content="", tool_calls=[{
            "id": "tc-read", "name": "read_file", "args": {"file_path": a}
        }]),
        ToolMessage(content="File content", name="read_file",
                    tool_call_id="tc-read", status="success"),
    ]
    partial = summarize_checkpoint_evidence({
        "messages": msgs, "files": {a: "some data"}
    }, termination_reason="graph_recursion_limit")
    assert partial["status"] == "incomplete"
    assert partial["successful_tools"] == ["write_file", "read_file"]
    assert a in partial["virtual_artifact_paths"]
    assert a in partial["artifact_readback_paths"]
    assert partial["checkpoint_recovered"] is True
    assert partial["objective_verified"] is False
    assert "some data" not in str(partial)


def test_checkpoint_not_available_fails_closed_without_tools():
    partial = summarize_checkpoint_evidence(None, termination_reason="model_call_limit")
    assert partial["status"] == "incomplete"
    assert partial["virtual_artifact_paths"] == []
    assert not partial["checkpoint_recovered"]
    assert not partial["objective_verified"]


def test_only_supported_termination_exceptions_trigger_recovery():
    GraphRecursionError = type("GraphRecursionError", (Exception,), {})
    ModelCallLimitExceededError = type("ModelCallLimitExceededError", (Exception,), {})
    assert controlled_termination_reason(GraphRecursionError()) == "graph_recursion_limit"
    assert controlled_termination_reason(ModelCallLimitExceededError()) == "model_call_limit"
    assert controlled_termination_reason(ValueError("not a limit")) is None



def test_real_langgraph_stops_repeated_virtual_tool_cycle_without_hosted_model(monkeypatch):
    """Actual DeepAgents graph, fake model, real virtual tool dispatch."""
    import asyncio
    from typing import Any
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langgraph.checkpoint.memory import MemorySaver
    from agent_platform.harness import build_frontier_agent

    class Scripted(FakeMessagesListChatModel):
        def bind_tools(self, tools: Any, **kwargs: Any):
            return self

    monkeypatch.setenv("DRAGONZPYDER_AGENT_STRESS_EVAL_ENABLED", "0")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_EVAL_ALLOW_PAID", "0")
    fake = Scripted(responses=[
        _model_tool("ls", {"path": "/workspace"}, i) for i in range(7)
    ])
    graph = build_frontier_agent(fake, MemorySaver())
    answer = asyncio.run(graph.ainvoke(
        {"messages": [{"role": "user", "content": "Inspect the workspace."}]},
        config={"configurable": {"thread_id": "live-graph-repetition-guard"},
                "recursion_limit": 64},
    ))
    assert answer["messages"][-1].content.startswith(STOP_PREFIX)
    assert "repeated_tool_cycle" in answer["messages"][-1].content
    assert len([m for m in answer["messages"] if getattr(m, "type", "") == "tool"]) >= 4


def test_runtime_recovers_checkpointed_evidence_on_real_graph_recursion_error(monkeypatch):
    """No model provider, but exercise AgentRuntime's full catch/recovery path."""
    import asyncio
    from types import SimpleNamespace
    from agent_platform import runtime

    GraphRecursionError = type("GraphRecursionError", (Exception,), {})
    path = "/workspace/partial-result.md"

    class FakeAgent:
        async def ainvoke(self, inputs, **kwargs):
            from langchain_core.messages import HumanMessage
            turn = inputs["messages"][0]
            self.current = HumanMessage(content=turn["content"], id=turn["id"])
            raise GraphRecursionError("bounded fake execution")

        async def aget_state(self, config):
            assert "configurable" in config and "thread_id" in config["configurable"]
            return SimpleNamespace(values={
                "messages": [
                    self.current,
                    AIMessage(content="", tool_calls=[{
                        "id": "t1", "name": "write_file",
                        "args": {"file_path": path, "content": "offline test"}
                    }]),
                    ToolMessage(content="wrote", name="write_file",
                                tool_call_id="t1", status="success"),
                ],
                "files": {path: "offline test"},
            })

    monkeypatch.setattr(runtime, "model_client", lambda: object())
    monkeypatch.setattr(runtime, "build_agent", lambda model, cp: FakeAgent())
    monkeypatch.delenv("DRAGONZPYDER_STAGING_LANGFUSE_ENABLED", raising=False)
    runner = runtime.AgentRuntime()
    runner._checkpointer = object()  # No database or network
    report = asyncio.run(runner.run_report(
        service_id="frontier-stress", thread_id="simulated-recovery",
        prompt="Complete the task.",
        recover_partial_on_failure=True,
    ))
    assert report["status"] == "incomplete"
    assert report["termination_reason"] == "graph_recursion_limit"
    assert report["checkpoint_recovered"]
    assert report["successful_tools"] == ["write_file"]
    assert path in report["virtual_artifact_paths"]
    assert report["objective_verified"] is False



def test_langfuse_callback_cannot_attach_to_user_prompt_smoke(monkeypatch):
    """Even with credentials, only synthetic benchmark services opt in."""
    from agent_platform.runtime import telemetry_callbacks
    monkeypatch.setenv("DRAGONZPYDER_STAGING_LANGFUSE_ENABLED", "1")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-offline")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-offline")
    monkeypatch.setenv("LANGFUSE_BASE_URL", "https://us.cloud.langfuse.com")
    assert telemetry_callbacks("agent-smoke") == []
    assert telemetry_callbacks("personal-chat") == []
    monkeypatch.setenv("DRAGONZPYDER_STAGING_LANGFUSE_ENABLED", "0")
    assert telemetry_callbacks("frontier-stress") == []



def test_subagent_stops_after_five_ai_turns_without_model_spend():
    from agent_platform.progress_guard import (
        MAX_SPECIALIST_TURNS, specialist_progress_decision,
    )
    assert MAX_SPECIALIST_TURNS == 5
    messages=[AIMessage(content="progress") for _ in range(5)]
    decision=specialist_progress_decision({"messages":messages})
    assert decision["jump_to"]=="end"
    assert decision["messages"][0].content.startswith(STOP_PREFIX)
    assert "specialist_step_budget_exhausted" in decision["messages"][0].content
    assert specialist_progress_decision({"messages":messages[:4]}) is None


def test_new_human_turn_resets_checkpoint_step_budget_and_repetition():
    from langchain_core.messages import HumanMessage
    from agent_platform.progress_guard import current_turn_messages, MAX_NORMAL_TURNS
    old = [HumanMessage(content="old turn")] + [
        AIMessage(content="prior answer") for _ in range(MAX_NORMAL_TURNS + 2)
    ]
    current = [HumanMessage(content="new turn"), AIMessage(content="new answer")]
    assert len(current_turn_messages(old + current)) == 2
    assert stop_reason(old + current, stress_mode=False) is None

    old_calls = [HumanMessage(content="older request")] + [
        _model_tool("operly_tasks_list", {"limit": 1}, i) for i in range(4)
    ]
    assert stop_reason(old_calls, stress_mode=False) == "repeated_tool_cycle"
    assert stop_reason(old_calls + [HumanMessage(content="a different request")],
                       stress_mode=False) is None


def test_current_turn_tool_receipts_exclude_prior_checkpointed_calls():
    from langchain_core.messages import HumanMessage
    msgs = [
        HumanMessage(content="list tasks"),
        _model_tool("operly_tasks_list", {}, 1),
        ToolMessage(content="tasks returned", name="operly_tasks_list",
                    tool_call_id="run-1", status="success"),
        AIMessage(content="Tasks listed"),
        HumanMessage(content="What's the earlier marker?"),
        AIMessage(content="ORBIT-7319"),
    ]
    current = summarize_agent_result({"messages": msgs})
    assert current["successful_tools"] == []
    assert current["failed_tool_count"] == 0

    follow = [
        HumanMessage(content="list the tasks again"),
        _model_tool("operly_tasks_list", {}, 2),
        ToolMessage(content="new tasks", name="operly_tasks_list",
                    tool_call_id="run-2", status="success"),
        AIMessage(content="Listed the tasks again"),
    ]
    report = summarize_agent_result({"messages": msgs + follow})
    assert report["successful_tools"] == ["operly_tasks_list"]


def test_changing_read_observations_are_not_stagnant():
    messages = []
    for i in range(4):
        messages.extend([
            _model_tool("operly_workflow_list", {}, i),
            ToolMessage(content=f'{{"records": [{i}]}}', name="operly_workflow_list",
                        tool_call_id=f"run-{i}", status="success"),
        ])
    assert stop_reason(messages, stress_mode=False) is None
    for message in messages:
        if isinstance(message, ToolMessage):
            message.content = '{"records": [1]}'
    assert stop_reason(messages, stress_mode=False) == "repeated_tool_cycle"


def test_approval_control_stops_real_deepagents_before_another_model_call(monkeypatch):
    """Actual graph + upstream middleware + real tool, no external provider."""
    import asyncio
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langchain_core.tools import tool
    from langgraph.checkpoint.memory import MemorySaver
    from agent_platform.harness import build_frontier_agent

    calls = []

    @tool
    async def operly_update_record() -> str:
        """Request approval for a synthetic record change."""
        calls.append("request")
        return '{"status": "waiting_for_approval", "approval_id": "synthetic"}'

    class Scripted(FakeMessagesListChatModel):
        def bind_tools(self, tools, **kwargs):
            return self

    monkeypatch.setenv("DRAGONZPYDER_OPERLY_TOOLS_ENABLED", "1")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_WEB_SEARCH_ENABLED", "0")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_QUICKJS_ENABLED", "0")
    model = Scripted(responses=[
        _model_tool("operly_update_record", {}, 1),
        _model_tool("operly_update_record", {}, 2),
        AIMessage(content="Wrongly claimed completion"),
    ])
    graph = build_frontier_agent(model, MemorySaver(), delegated_tools=[operly_update_record])
    result = asyncio.run(graph.ainvoke(
        {"messages": [{"role": "user", "content": "Request a record change"}]},
        config={"configurable": {"thread_id": "approval-guard"}, "recursion_limit": 128},
    ))
    assert calls == ["request"]
    report = summarize_agent_result(result)
    assert report["status"] == "incomplete"
    assert report["termination_reason"] == "external_approval_required"
    assert report["successful_tools"] == []
    assert report["failed_tool_count"] == 1
    assert report["objective_verified"] is False


def test_structured_tool_errors_are_not_success_receipts():
    from langchain_core.messages import HumanMessage
    from agent_platform.tool_outcomes import tool_outcome
    cases = [
        ('{"ok":false,"error_code":"bad_input"}', None, "failed"),
        ('{"status":"waiting_for_approval"}', None, "approval_required"),
        ([{"type":"text","text":'{"status":"outcome_unconfirmed"}'}], None, "unknown"),
        ("transport returned", {"structured_content":{"isError":True}}, "failed"),
        ('{"result":[{"status":"failed"},{"status":"pending_approval"}]}', None, "returned"),
        ('[{"status":"failed"}]', None, "returned"),
    ]
    for index, (content, artifact, expected) in enumerate(cases):
        message = ToolMessage(content=content, artifact=artifact, name="operly_workflow_list",
                              tool_call_id=str(index), status="success")
        assert tool_outcome(message) == expected
        report = summarize_checkpoint_evidence(
            {"messages":[HumanMessage(content="inspect"),message]},
            termination_reason="model_call_limit")
        assert report["successful_tools"] == (["operly_workflow_list"] if expected == "returned" else [])
        assert report["failed_tool_count"] == int(expected != "returned")


def test_runtime_rejects_stale_partial_checkpoint_even_for_identical_prompt(monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from langchain_core.messages import HumanMessage
    from agent_platform import runtime

    class GraphRecursionError(Exception):
        pass

    class FakeAgent:
        calls = 0
        async def ainvoke(self, inputs, config):
            self.calls += 1
            assert config["recursion_limit"] >= 128
            raise GraphRecursionError()
        async def aget_state(self, config):
            return SimpleNamespace(values={"messages":[
                HumanMessage(content="repeat", id="old-turn"),
                ToolMessage(content="old data", name="old_tool", tool_call_id="old"),
                AIMessage(content="old answer"),
            ]})

    agent = FakeAgent()
    monkeypatch.setattr(runtime, "model_client", lambda: object())
    monkeypatch.setattr(runtime, "build_agent", lambda model, cp: agent)
    runner = runtime.AgentRuntime()
    runner._checkpointer = object()
    report = asyncio.run(runner.run_report(service_id="offline-test", thread_id="same",
                       prompt="repeat", recover_partial_on_failure=True))
    assert agent.calls == 1
    assert report["status"] == "incomplete"
    assert report["checkpoint_recovered"] is False
    assert report["successful_tools"] == []
    assert report["objective_verified"] is False


def test_execution_limits_do_not_enable_stress_with_partial_flags(monkeypatch):
    from agent_platform.execution_contract import execution_limits, _STRESS_FLAGS
    for flag in _STRESS_FLAGS:
        monkeypatch.delenv(flag, raising=False)
    assert execution_limits().deadline_seconds == 90
    assert execution_limits().graph_supersteps == 128
    for flag in _STRESS_FLAGS[:-1]:
        monkeypatch.setenv(flag, "1")
    assert execution_limits().deadline_seconds == 90
    monkeypatch.setenv(_STRESS_FLAGS[-1], "1")
    assert execution_limits().deadline_seconds == 220
    assert execution_limits(parent_job=True).deadline_seconds == 110
