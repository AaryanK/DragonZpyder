"""No-cost integration contracts for the opt-in Deep Agents harness."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_harness_uses_real_deepagents_and_is_agentic():
    from langchain_openrouter import ChatOpenRouter
    from langgraph.checkpoint.memory import MemorySaver
    from agent_platform.harness import build_frontier_agent
    model = ChatOpenRouter(model="openai/gpt-oss-120b", api_key="test")
    agent = build_frontier_agent(model, MemorySaver())
    assert hasattr(agent, "ainvoke")
    assert hasattr(agent, "astream")
    assert hasattr(agent, "aget_state")


def test_specialists_cannot_inherit_external_tools():
    from agent_platform.harness import specialist_specs, VIRTUAL_TOOLS
    specs = specialist_specs()
    assert {p["name"] for p in specs} == {"analyst", "verifier", "builder"}
    assert specs[0]["tools"] == []
    assert {tool.name for tool in specs[1]["tools"]} == {
        "check_quadratic_gradient_step", "check_trilinear_interpolation"}
    assert specs[2]["tools"] == []
    assert all(len(p["middleware"]) == 2 for p in specs)
    supplied = object()
    overridden = specialist_specs({"verifier": supplied})
    assert overridden[1]["model"] is supplied
    assert "model" not in overridden[0]
    assert all("execute" not in str(p["tools"]) for p in specs)
    assert "write_file" in VIRTUAL_TOOLS
    assert "edit_file" in VIRTUAL_TOOLS
    assert "execute" not in VIRTUAL_TOOLS
    assert "delete" not in VIRTUAL_TOOLS


def test_legacy_remains_default_and_feature_flag_selects_v2(monkeypatch):
    from langchain_openrouter import ChatOpenRouter
    from langgraph.checkpoint.memory import MemorySaver
    from agent_platform.runtime import build_agent
    model = ChatOpenRouter(model="openai/gpt-oss-120b", api_key="test")
    monkeypatch.delenv("DRAGONZPYDER_AGENT_HARNESS_V2", raising=False)
    legacy = build_agent(model, MemorySaver())
    assert hasattr(legacy, "ainvoke")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_HARNESS_V2", "1")
    frontier = build_agent(model, MemorySaver())
    assert hasattr(frontier, "ainvoke")



def test_virtual_artifact_written_by_real_langgraph_tool_loop():
    """Exercise actual tool dispatch without a hosted model or real filesystem."""
    import asyncio
    from typing import Any

    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langchain_core.messages import AIMessage, ToolMessage
    from langgraph.checkpoint.memory import MemorySaver
    from agent_platform.harness import build_frontier_agent

    class Scripted(FakeMessagesListChatModel):
        def bind_tools(self, tools: Any, **kwargs: Any):
            return self

    fake = Scripted(responses=[
        AIMessage(content="", tool_calls=[{
            "name": "write_file",
            "args": {"file_path": "/workspace/result.md", "content": "a useful artifact"},
            "id": "write-1",
        }]),
        AIMessage(content="", tool_calls=[{
            "name": "read_file",
            "args": {"file_path": "/workspace/result.md"},
            "id": "read-1",
        }]),
        AIMessage(content="I created and re-read /workspace/result.md."),
    ])
    agent = build_frontier_agent(fake, MemorySaver())
    config = {"configurable": {"thread_id": "synthetic-artifact-test"}}
    result = asyncio.run(agent.ainvoke(
        {"messages": [{"role": "user", "content": "Create a working-note artifact"}]},
        config=config,
    ))
    tool_replies = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert any(m.name == "write_file" for m in tool_replies)
    assert not any("error" in str(m.content).lower() for m in tool_replies)
    assert "result.md" in result["messages"][-1].content
    from agent_platform.runtime import summarize_agent_result
    report = summarize_agent_result(result)
    assert report["artifact_readback_paths"] == ["/workspace/result.md"]



def test_specialist_model_must_use_gateway_allowlist(monkeypatch):
    import pytest
    from agent_platform.runtime import model_client
    monkeypatch.setenv("DRAGONZPYDER_RUNTIME_ALLOWED_MODELS", "openai/gpt-oss-120b")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_USE_GATEWAY", "1")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_GATEWAY_TOKEN", "t" * 44)
    monkeypatch.setenv("DRAGONZPYDER_AGENT_GATEWAY_BASE_URL", "https://gateway.example.org/internal/agent/v1")
    with pytest.raises(RuntimeError, match="allowlist"):
        model_client(model_override="unapproved/expensive-model")
    assert model_client(model_override="openai/gpt-oss-120b") is not None



def test_run_report_contains_evidence_but_does_not_claim_objective_verified():
    from langchain_core.messages import AIMessage, ToolMessage
    from agent_platform.runtime import summarize_agent_result
    result = {
        "messages": [
            AIMessage(content="", tool_calls=[{"name": "write_file", "args": {
                "file_path": "/workspace/test.md", "content": "hello"}, "id": "tc1"}]),
            ToolMessage(content="File written", tool_call_id="tc1",
                        name="write_file", status="success"),
            AIMessage(content="Drafted a virtual artifact."),
        ],
        "files": {"/workspace/test.md": object()},
        "todos": [{"content": "Draft a note", "status": "completed"}],
    }
    report = summarize_agent_result(result)
    assert report["answer"] == "Drafted a virtual artifact."
    assert report["successful_tools"] == ["write_file"]
    assert report["virtual_artifact_paths"] == ["/workspace/test.md"]
    assert report["artifact_readback_paths"] == []
    assert report["objective_verified"] is False



def test_stress_output_token_ceiling_requires_both_paid_eval_flags(monkeypatch):
    from agent_platform.runtime import model_client
    monkeypatch.setenv("DRAGONZPYDER_RUNTIME_ALLOWED_MODELS", "openai/gpt-oss-120b")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_USE_GATEWAY", "1")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_GATEWAY_TOKEN", "t" * 44)
    monkeypatch.setenv("DRAGONZPYDER_AGENT_GATEWAY_BASE_URL",
                       "https://gateway.example.org/internal/agent/v1")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_STRESS_EVAL_ENABLED", "1")
    monkeypatch.delenv("DRAGONZPYDER_AGENT_EVAL_ALLOW_PAID", raising=False)
    normal = model_client(model_override="openai/gpt-oss-120b")
    assert normal.max_tokens == 768
    assert normal.max_retries == 0
    monkeypatch.setenv("DRAGONZPYDER_AGENT_EVAL_ALLOW_PAID", "1")
    stress = model_client(model_override="openai/gpt-oss-120b")
    assert stress.max_tokens == 2048
    assert stress.max_retries == 1


def test_quickjs_interpreter_is_opt_in_and_has_no_host_or_external_bridges(monkeypatch):
    import asyncio
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langchain_core.messages import AIMessage
    from langgraph.checkpoint.memory import MemorySaver
    from agent_platform.harness import build_frontier_agent

    class ToolCapture(FakeMessagesListChatModel):
        captured: set[str] | None = None

        def bind_tools(self, tools, **kwargs):
            self.captured = {getattr(tool, "name", None) for tool in tools}
            return self

    def run(enabled):
        monkeypatch.setenv("DRAGONZPYDER_AGENT_QUICKJS_ENABLED", "1" if enabled else "0")
        model = ToolCapture(responses=[AIMessage(content="Finished the synthetic test.")])
        graph = build_frontier_agent(model, MemorySaver())
        result = asyncio.run(graph.ainvoke(
            {"messages": [{"role": "user", "content": "Do nothing; report finished"}]},
            config={"configurable": {"thread_id": "quickjs-on" if enabled else "quickjs-off"}},
        ))
        assert "Finished" in result["messages"][-1].content
        return model.captured

    off = run(False)
    on = run(True)
    assert off is not None and "eval" not in off
    assert on is not None and "eval" in on
    assert "execute" not in on


def test_parallel_paid_mode_is_off_by_default_even_with_parent_runtime(monkeypatch):
    import asyncio
    import pytest
    from agent_platform.runtime import AgentRuntime
    for key in (
        "DRAGONZPYDER_AGENT_PARALLEL_EVAL_ENABLED",
        "DRAGONZPYDER_AGENT_STRESS_EVAL_ENABLED",
        "DRAGONZPYDER_AGENT_EVAL_ALLOW_PAID",
    ):
        monkeypatch.delenv(key, raising=False)
    runtime = AgentRuntime()
    runtime._checkpointer = object()  # no Postgres side effects
    with pytest.raises(RuntimeError, match="disabled"):
        asyncio.run(runtime.run_parallel_report(
            service_id="offline-synthetic", thread_id="test",
            tracks=[{"id": "a", "prompt": "a"}, {"id": "b", "prompt": "b"}],
        ))


def test_virtual_filesystem_denies_escape_outside_workspace(monkeypatch):
    """Actual LangGraph tool call: outside-workspace writes stay forbidden."""
    import asyncio
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langchain_core.messages import AIMessage, ToolMessage
    from langgraph.checkpoint.memory import MemorySaver
    from agent_platform.harness import build_frontier_agent

    class Scripted(FakeMessagesListChatModel):
        def bind_tools(self, tools, **kwargs):
            return self

    monkeypatch.setenv("DRAGONZPYDER_AGENT_QUICKJS_ENABLED", "0")
    model = Scripted(responses=[
        AIMessage(content="", tool_calls=[{
            "name": "write_file",
            "args": {"file_path": "/private/blocked.md", "content": "not allowed"},
            "id": "write-outside",
        }]),
        AIMessage(content="The attempted write was not authorized."),
    ])
    graph = build_frontier_agent(model, MemorySaver())
    result = asyncio.run(graph.ainvoke(
        {"messages": [{"role": "user", "content": "Write a private file"}]},
        config={"configurable": {"thread_id": "permission-check"}},
    ))
    assert "/private/blocked.md" not in result.get("files", {})
    responses = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert responses
    assert any(("permission" in str(m.content).lower()
                or getattr(m, "status", "") == "error") for m in responses)


def test_builder_model_override_is_actually_routed_to_specialist(monkeypatch):
    """Previously the builder override was preflighted but never instantiated."""
    from agent_platform import runtime, harness
    from langgraph.checkpoint.memory import MemorySaver

    calls = []
    captured = {}

    def fake_model_client(*, model_override=None):
        calls.append(model_override)
        if model_override == "unapproved/model":
            raise RuntimeError("Agent model must be in the DragonZpyder allowlist")
        return "approved:" + str(model_override)

    def fake_build(model, checkpointer, *, specialist_models=None):
        captured.update(specialist_models)
        return object()

    monkeypatch.setenv("DRAGONZPYDER_AGENT_HARNESS_V2", "1")
    for role in ("ANALYST", "VERIFIER", "RESEARCHER", "BUILDER"):
        monkeypatch.delenv("DRAGONZPYDER_AGENT_" + role + "_MODEL_ID", raising=False)
    monkeypatch.setenv("DRAGONZPYDER_AGENT_BUILDER_MODEL_ID", "approved/builder")
    monkeypatch.setattr(runtime, "model_client", fake_model_client)
    monkeypatch.setattr(harness, "build_frontier_agent", fake_build)
    runtime.build_agent(object(), MemorySaver())
    assert captured["builder"] == "approved:approved/builder"
    assert calls == ["approved/builder"]


def test_builder_model_override_fails_closed_when_not_allowlisted(monkeypatch):
    import pytest
    from agent_platform.runtime import build_agent
    from langgraph.checkpoint.memory import MemorySaver

    monkeypatch.setenv("DRAGONZPYDER_AGENT_HARNESS_V2", "1")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_BUILDER_MODEL_ID", "unapproved/expensive")
    monkeypatch.setenv("DRAGONZPYDER_RUNTIME_ALLOWED_MODELS", "openai/gpt-oss-120b")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_USE_GATEWAY", "1")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_GATEWAY_TOKEN", "t" * 44)
    monkeypatch.setenv("DRAGONZPYDER_AGENT_GATEWAY_BASE_URL",
                       "https://gateway.example.org/internal/agent/v1")
    with pytest.raises(RuntimeError, match="allowlist"):
        build_agent(object(), MemorySaver())


def test_paid_parallel_fanout_fails_closed_even_with_all_operator_flags(monkeypatch):
    """No parent-atomic gateway reservation exists: env flags cannot fake one."""
    import asyncio
    import pytest
    from agent_platform.runtime import AgentRuntime

    for flag in (
        "DRAGONZPYDER_AGENT_PARALLEL_EVAL_ENABLED",
        "DRAGONZPYDER_AGENT_STRESS_EVAL_ENABLED",
        "DRAGONZPYDER_AGENT_EVAL_ALLOW_PAID",
        "DRAGONZPYDER_AGENT_USE_GATEWAY",
        "DRAGONZPYDER_AGENT_PRODUCTION_MODE",
        "DRAGONZPYDER_AGENT_HARNESS_V2",
    ):
        monkeypatch.setenv(flag, "1")
    runtime = AgentRuntime()
    runtime._checkpointer = object()  # No DB, network, or model calls.
    tracks = [{"id": "one", "prompt": "Analyze evidence"},
              {"id": "two", "prompt": "Verify results"}]
    with pytest.raises(RuntimeError, match="atomic shared gateway budget"):
        asyncio.run(runtime.run_parallel_report(
            service_id="staging", thread_id="budget-test", tracks=tracks,
        ))


def test_parallel_guard_cannot_be_bypassed_by_a_budget_claim_env(monkeypatch):
    """A self-declared environment variable is not server-side enforcement."""
    import asyncio
    import pytest
    from agent_platform.runtime import AgentRuntime
    for flag in (
        "DRAGONZPYDER_AGENT_PARALLEL_EVAL_ENABLED",
        "DRAGONZPYDER_AGENT_STRESS_EVAL_ENABLED",
        "DRAGONZPYDER_AGENT_EVAL_ALLOW_PAID",
        "DRAGONZPYDER_AGENT_USE_GATEWAY",
        "DRAGONZPYDER_AGENT_PRODUCTION_MODE",
        "DRAGONZPYDER_AGENT_HARNESS_V2",
    ):
        monkeypatch.setenv(flag, "1")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_SHARED_BUDGET_ENFORCED", "1")
    runtime = AgentRuntime()
    runtime._checkpointer = object()
    with pytest.raises(RuntimeError, match="atomic shared gateway budget"):
        asyncio.run(runtime.run_parallel_report(
            service_id="staging", thread_id="claimed-budget",
            tracks=[{"id": "a", "prompt": "a"}, {"id": "b", "prompt": "b"}],
        ))
