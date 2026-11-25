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
