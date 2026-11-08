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
        async def ainvoke(self, *args, **kwargs):
            raise GraphRecursionError("bounded fake execution")

        async def aget_state(self, config):
            assert "configurable" in config and "thread_id" in config["configurable"]
            return SimpleNamespace(values={
                "messages": [
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
