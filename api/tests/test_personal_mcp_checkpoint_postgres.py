"""Real LangGraph PostgresSaver continuation across process-like saver restart.

No provider/model calls or network tools. Persist and resume true LangGraph
messages with the same per-user Personal thread, then prove isolation when
another signed-in user requests the same conversation identifier.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
import sys
from uuid import uuid4

from langchain_core.messages import AIMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, MessagesState, StateGraph

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_platform.personal_bridge import personal_thread


def _graph(saver):
    def reply(state: MessagesState):
        last_user = next(
            msg.content for msg in reversed(state["messages"])
            if msg.type == "human"
        )
        return {"messages": [AIMessage(content="ack:" + last_user)]}
    builder = StateGraph(MessagesState)
    builder.add_node("reply", reply)
    builder.add_edge(START, "reply")
    builder.add_edge("reply", END)
    return builder.compile(checkpointer=saver)


def test_true_postgres_checkpoint_continues_after_saver_restart_and_isolates_users():
    dsn = os.environ["DRAGONZPYDER_BUDGET_TEST_DSN"]
    conversation = str(uuid4())
    user_a, user_b = str(uuid4()), str(uuid4())
    config_a = {"configurable": {"thread_id": personal_thread(user_a, conversation)}}
    config_b = {"configurable": {"thread_id": personal_thread(user_b, conversation)}}

    async def run():
        async with AsyncPostgresSaver.from_conn_string(dsn) as saver:
            await saver.setup()
            graph = _graph(saver)
            output = await graph.ainvoke(
                {"messages": [{"role": "user", "content": "first authorized wake"}]},
                config=config_a,
            )
            assert output["messages"][-1].content == "ack:first authorized wake"
        # Deliberately close the saver and construct a new graph with no
        # in-memory state. Only PostgreSQL preserves wake-one messages.
        async with AsyncPostgresSaver.from_conn_string(dsn) as saver2:
            graph2 = _graph(saver2)
            saved = await graph2.aget_state(config_a)
            assert any(msg.content == "first authorized wake"
                       for msg in saved.values["messages"])
            output2 = await graph2.ainvoke(
                {"messages": [{"role": "user", "content": "second authorized wake"}]},
                config=config_a,
            )
            contents = [msg.content for msg in output2["messages"]]
            assert "first authorized wake" in contents
            assert "second authorized wake" in contents
            assert "ack:first authorized wake" in contents
            assert "ack:second authorized wake" in contents

            # The other user has a different checkpoint namespace even
            # when the externally supplied conversation string is identical.
            foreign = await graph2.aget_state(config_b)
            assert not foreign.values
            other = await graph2.ainvoke(
                {"messages": [{"role": "user", "content": "user B private wake"}]},
                config=config_b,
            )
            others = [msg.content for msg in other["messages"]]
            assert "user B private wake" in others
            assert "first authorized wake" not in others
            assert "second authorized wake" not in others

    asyncio.run(run())
