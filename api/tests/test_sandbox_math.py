"""Execute a scripted numerical check through real WASM QuickJS, no provider.

This is a restricted JavaScript arithmetic sandbox, not a Python/OS sandbox.
"""
import asyncio
from typing import Any

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from agent_platform.harness import build_frontier_agent


def test_wasm_quickjs_executes_scientific_arithmetic_without_host_bridges(monkeypatch):
    class Scripted(FakeMessagesListChatModel):
        def bind_tools(self, tools: Any, **kwargs: Any):
            return self

    monkeypatch.setenv("DRAGONZPYDER_AGENT_QUICKJS_ENABLED","1")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_STRESS_EVAL_ENABLED","0")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_EVAL_ALLOW_PAID","0")
    fake=Scripted(responses=[
        AIMessage(content="",tool_calls=[{
            "name":"eval",
            "args":{"code":"console.log(5 - 0.1 * (-10)); console.log(typeof fetch); console.log(typeof process);"},
            "id":"js-check-1",
        }]),
        AIMessage(content="The arithmetic is 6, and the sandbox has no host bridge."),
    ])
    graph=build_frontier_agent(fake,MemorySaver())
    result=asyncio.run(graph.ainvoke(
        {"messages":[{"role":"user","content":"Check a numerical step locally"}]},
        config={"configurable":{"thread_id":"offline-quickjs-scientific"},
                "recursion_limit":30},
    ))
    replies=[x for x in result["messages"]
             if isinstance(x,ToolMessage) and x.name=="eval"]
    assert replies, "The agent must execute the eval tool"
    content=str(replies[0].content)
    assert "6" in content, content
    assert "undefined" in content, content
    assert "/etc/passwd" not in content
