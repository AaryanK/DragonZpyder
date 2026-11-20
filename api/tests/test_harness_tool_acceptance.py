"""Zero-provider, real LangGraph tool-loop acceptance tests.

These exercise actual Deep Agents filesystem dispatch and checkpoint state
with scripted AIMessage responses. They do NOT establish live model quality
or authorize host filesystem, network, or business tools.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
import sys
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver

from agent_platform.harness import build_frontier_agent
from agent_platform.runtime import summarize_agent_result


class ToolScript(FakeMessagesListChatModel):
    def bind_tools(self, tools, **kwargs):
        # The harness still constructs and executes the real LangGraph tools.
        return self


def scripted_call(name: str, arguments: dict) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{
            "name": name,
            "args": arguments,
            "id": "call_" + uuid4().hex,
            "type": "tool_call",
        }],
    )


def test_v2_real_virtual_write_read_and_checkpoint_roundtrip(monkeypatch):
    """A claimed file is insufficient; both real tool receipts must exist."""
    monkeypatch.delenv("DRAGONZPYDER_AGENT_WEB_SEARCH_ENABLED", raising=False)
    monkeypatch.delenv("DRAGONZPYDER_AGENT_QUICKJS_ENABLED", raising=False)
    path = "/workspace/acceptance.txt"
    expected = "DRAGONZPYDER_TOOL_RECEIPT_391"
    model = ToolScript(responses=[
        scripted_call("write_file", {"file_path": path, "content": expected}),
        scripted_call("read_file", {"file_path": path}),
        AIMessage(content="The file was written and read back."),
    ])
    checkpointer = MemorySaver()
    config = {"configurable": {"thread_id": "acceptance-tool-roundtrip"}}

    async def run():
        agent = build_frontier_agent(model, checkpointer)
        state = await agent.ainvoke(
            {"messages": [{"role": "user", "content": "Write and read the test file."}]},
            config=config,
        )
        report = summarize_agent_result(state)
        assert report["status"] == "completed"
        assert "write_file" in report["successful_tools"]
        assert "read_file" in report["successful_tools"]
        assert path in report["virtual_artifact_paths"]
        assert path in report["artifact_readback_paths"]
        assert expected in str(state["files"][path])
        # Reconstructing the graph must not erase the checkpointed file.
        another_agent = build_frontier_agent(
            ToolScript(responses=[AIMessage(content="No action needed.")]),
            checkpointer,
        )
        snapshot = await another_agent.aget_state(config)
        assert path in snapshot.values["files"]
        assert expected in str(snapshot.values["files"][path])
        # Tool dispatch and checkpoint alone cannot certify objective correctness.
        assert report["objective_verified"] is False

    asyncio.run(run())


def test_v2_rejects_virtual_filesystem_escape(monkeypatch):
    """An agent-issued write outside /workspace must not persist."""
    monkeypatch.delenv("DRAGONZPYDER_AGENT_WEB_SEARCH_ENABLED", raising=False)
    monkeypatch.delenv("DRAGONZPYDER_AGENT_QUICKJS_ENABLED", raising=False)
    target = "/private/credentials.txt"
    model = ToolScript(responses=[
        scripted_call("write_file", {"file_path": target, "content": "do-not-write"}),
        AIMessage(content="Cannot write outside the authorized virtual workspace."),
    ])

    async def run():
        agent = build_frontier_agent(model, MemorySaver())
        state = await agent.ainvoke(
            {"messages": [{"role": "user", "content": "Write to a forbidden path."}]},
            config={"configurable": {"thread_id": "acceptance-denied-write"}},
        )
        assert target not in state.get("files", {})
        # A denial must not be counted as a verified external action.
        report = summarize_agent_result(state)
        assert report["objective_verified"] is False

    asyncio.run(run())


def test_simulated_business_tools_real_graph_approval_and_replay(monkeypatch):
    """Actual LangGraph dispatch: read, preview, reject, commit, replay, verify."""
    import json
    from langchain_core.messages import ToolMessage
    from agent_platform.synthetic_business_tools import SyntheticBusiness

    monkeypatch.setenv("DRAGONZPYDER_SYNTHETIC_TOOLS_ENABLED", "1")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_WEB_SEARCH_ENABLED", "0")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_QUICKJS_ENABLED", "0")
    fake = SyntheticBusiness()
    fake.approvals.add("approved-test-1")
    model = ToolScript(responses=[
        scripted_call("lookup_inventory", {"sku": "coffee"}),
        scripted_call("simulate_order", {"sku": "coffee", "quantity": 2}),
        scripted_call("commit_order", {
            "sku": "coffee", "quantity": 2, "request_id": "order-1",
            "approval_id": "missing",
        }),
        scripted_call("commit_order", {
            "sku": "coffee", "quantity": 2, "request_id": "order-1",
            "approval_id": "approved-test-1",
        }),
        scripted_call("commit_order", {
            "sku": "coffee", "quantity": 2, "request_id": "order-1",
            "approval_id": "approved-test-1",
        }),
        scripted_call("lookup_order", {"request_id": "order-1"}),
        AIMessage(content="Simulated order completed; readback confirmed."),
    ])
    async def run():
        graph = build_frontier_agent(model, MemorySaver(), synthetic_tools=fake.tools())
        state = await graph.ainvoke(
            {"messages": [{"role": "user", "content": "Run simulated inventory workflow."}]},
            config={"configurable": {"thread_id": "synthetic-business-roundtrip"}},
        )
        receipts = [json.loads(m.content) for m in state["messages"]
                    if isinstance(m, ToolMessage) and m.name in {
                        "lookup_inventory", "simulate_order", "commit_order", "lookup_order"}]
        assert len(receipts) == 6
        assert receipts[0]["quantity"] == 7
        assert receipts[1]["requires_approval"] is True
        assert receipts[2]["code"] == "approval_required"
        assert receipts[3]["ok"] and receipts[3]["replayed"] is False
        assert receipts[4]["ok"] and receipts[4]["replayed"] is True
        assert receipts[5]["receipt"]["request_id"] == "order-1"
        assert fake.inventory["coffee"] == 5
        assert len(fake.receipts) == 1
        report = summarize_agent_result(state)
        assert report["objective_verified"] is False
        assert "commit_order" in report["successful_tools"]
    asyncio.run(run())


def test_simulated_business_denials_and_transient_recovery():
    """The simulated provider, not the model, enforces permissions and dedup."""
    import json
    from agent_platform.synthetic_business_tools import SyntheticBusiness
    fake = SyntheticBusiness(fail_next_commit=True)
    tools = {tool.name: tool for tool in fake.tools()}

    async def call(name, args):
        return json.loads(await tools[name].ainvoke(args))

    async def run():
        base = {"sku": "coffee", "quantity": 2, "request_id": "r-77",
                "approval_id": "auth-77"}
        denied = await call("commit_order", base)
        assert denied["code"] == "approval_required"
        assert fake.inventory["coffee"] == 7
        fake.approvals.add("auth-77")
        failure = await call("commit_order", base)
        assert failure["code"] == "transient_failure" and failure["retryable"]
        assert fake.inventory["coffee"] == 7
        accepted = await call("commit_order", base)
        assert accepted["ok"] and not accepted["replayed"]
        replay = await call("commit_order", base)
        assert replay["ok"] and replay["replayed"]
        conflict = await call("commit_order", {**base, "quantity": 3})
        assert conflict["code"] == "idempotency_conflict"
        assert fake.inventory["coffee"] == 5
        assert len(fake.receipts) == 1
    asyncio.run(run())


def test_synthetic_tools_must_be_explicitly_enabled(monkeypatch):
    import pytest
    from agent_platform.synthetic_business_tools import SyntheticBusiness
    monkeypatch.delenv("DRAGONZPYDER_SYNTHETIC_TOOLS_ENABLED", raising=False)
    with pytest.raises(ValueError, match="disabled"):
        build_frontier_agent(
            ToolScript(responses=[AIMessage(content="no action")]),
            MemorySaver(), synthetic_tools=SyntheticBusiness().tools(),
        )
