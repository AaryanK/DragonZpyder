import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
from fastapi import HTTPException
from langchain_core.messages import AIMessageChunk
from agent_platform import first_party_chat as native


def test_stream_projects_root_public_text_and_never_tool_payloads():
    class Agent:
        async def astream(self, *args, **kwargs):
            assert kwargs["subgraphs"] is False
            yield "messages", (AIMessageChunk(content="private subagent", id="s"), {"langgraph_node":"subagent"})
            yield "messages", (AIMessageChunk(content=[{"type":"reasoning","reasoning":"internal"},{"type":"text","text":"Draft"}], id="a"), {"langgraph_node":"model","langgraph_step":1})
            yield "messages", (AIMessageChunk(content="", id="a", tool_call_chunks=[{"name":"test","args":"secret","id":"call","index":0}]), {"langgraph_node":"model","langgraph_step":1})
            yield "messages", (AIMessageChunk(content="Final", id="b"), {"langgraph_node":"model","langgraph_step":3})
            yield "values", {"messages":["checkpoint"]}
    events=[]
    result=asyncio.run(native._stream_agent(Agent(),{}, {},events.append))
    assert result == {"messages":["checkpoint"]}
    assert [x["text"] for x in events if x["type"]=="delta"] == ["Draft","Final"]
    assert "secret" not in str(events) and "internal" not in str(events) and "private subagent" not in str(events)
    assert any(x["type"]=="reset" for x in events)


def test_cancel_before_inference_does_not_call_agent():
    class Agent:
        ainvoke=AsyncMock()
    class DB:
        async def fetchval(self,*args): return True
    with pytest.raises(HTTPException) as err:
        asyncio.run(native._invoke_cancellable(Agent(),{}, {},DB(),"owner",uuid4(),None))
    assert err.value.status_code==409
    assert Agent.ainvoke.await_count==0


def test_cancel_inflight_stops_local_agent_without_claiming_rollback():
    async def scenario():
        stopped=asyncio.Event()
        class Agent:
            async def ainvoke(self,*args,**kwargs):
                try: await asyncio.Event().wait()
                finally: stopped.set()
        class DB:
            checks=0
            async def fetchval(self,*args):
                self.checks+=1
                return self.checks>1
        with pytest.raises(HTTPException) as err:
            await native._invoke_cancellable(Agent(),{}, {},DB(),"owner",uuid4(),None)
        assert err.value.status_code==409
        assert stopped.is_set()
    asyncio.run(scenario())


@pytest.mark.parametrize("failure", ["recursion", "timeout", "output_limit", "unknown", "none"])
def test_native_checkpoint_recovery_never_replays_or_credits_old_turn(failure):
    from types import SimpleNamespace
    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
    from langgraph.errors import GraphRecursionError

    class DB:
        async def fetchval(self, *args):
            return False

    class Agent:
        calls = 0
        values = None

        async def ainvoke(self, inputs, config):
            self.calls += 1
            turn = inputs["messages"][0]
            self.values = {"messages": [
                HumanMessage(content="same request", id="historical"),
                ToolMessage(content="old result", name="old_tool", tool_call_id="old"),
                AIMessage(content="old answer"),
                HumanMessage(content=turn["content"], id=turn["id"]),
                ToolMessage(content="new result", name="new_tool", tool_call_id="new"),
            ]}
            if failure == "recursion":
                raise GraphRecursionError("bounded")
            if failure == "timeout":
                raise TimeoutError("bounded")
            if failure == "output_limit":
                class GatewayFailure(Exception):
                    __module__ = "openai._exceptions"
                    status_code = 502
                    body = {"type": "dragonzpyder_inference_error", "code": "agent_output_limit_reached"}
                raise GatewayFailure("bounded")
            if failure == "unknown":
                raise RuntimeError("ambiguous")
            self.values["messages"].append(AIMessage(content="new answer"))
            return self.values

        async def aget_state(self, config):
            return SimpleNamespace(values=self.values)

    agent = Agent()
    run = native._run_checkpointed_turn(agent, "same request", {}, DB(), "owner", None, None)
    if failure == "unknown":
        with pytest.raises(HTTPException) as err:
            asyncio.run(run)
        assert err.value.status_code == 503
    else:
        report = asyncio.run(run)
        assert report["successful_tools"] == ["new_tool"]
        assert report["objective_verified"] is False
        assert report["status"] == ("completed" if failure == "none" else "incomplete")
        if failure != "none":
            assert report["termination_reason"] == {"recursion":"graph_recursion_limit",
                "timeout":"execution_deadline", "output_limit":"inference_output_limit_reached"}[failure]
    assert agent.calls == 1


def test_exact_turn_rejects_stale_duplicate_superseded_or_unfinished_state():
    from langchain_core.messages import HumanMessage, AIMessage
    h = HumanMessage(content="repeat", id="current")
    historical = HumanMessage(content="repeat", id="old")
    pending = AIMessage(content="", tool_calls=[{"name":"tool", "args":{}, "id":"call"}])
    for messages in ([historical, AIMessage(content="old answer")],
                     [h, h, AIMessage(content="answer")],
                     [h, historical, AIMessage(content="answer")],
                     [h, pending]):
        with pytest.raises(RuntimeError):
            native._exact_turn_state({"messages":messages}, "current", "repeat", require_answer=True)
    assert native._exact_turn_state({"messages":[historical,h,pending]},
        "current", "repeat", require_answer=False)["messages"] == [h,pending]
