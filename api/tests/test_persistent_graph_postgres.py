"""Real PostgreSQL graph acceptance: sequential receipts, replay and user isolation.

Tool provider is mocked; PostgreSQL, row locks, integrity checks, and the
production graph executor are real. This is NOT a live MCP performance test.
"""
import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import asyncpg

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agent_platform.persistent_graph import (
    SCHEMA, GraphStep, GraphWake, _sha, validate_plan,
    execute_graph_wake, graph_tools,
)
from agent_platform.mcp_broker import ToolReceipt, ToolOutcome


def _steps():
    return validate_plan([
        GraphStep(id="workflows",kind="mcp_read",capability_id="workflow.list"),
        GraphStep(id="tasks",kind="mcp_read",capability_id="tasks.list"),
        GraphStep(id="report",kind="compose",depends_on=["workflows","tasks"]),
        GraphStep(id="verify",kind="verify",depends_on=["report"]),
    ])


async def _fake_load(**kwargs):
    return [object()]


async def _fake_invoke(**kwargs):
    capability=kwargs["capability_id"]
    result={"ok":True,"capability":capability,
            "records": [{"id":capability+"-one"}]}
    return ToolOutcome(
        receipt=ToolReceipt(
            provider_id="operly",capability_id=capability,
            alias="operly_"+capability.replace(".","_"),
            arguments_sha256=_sha({}),
            result_sha256=_sha(result),
        ),
        result=result,
    )


async def _seed(dsn, *, user_id,session_id,conversation_id):
    plan=_steps()
    goal_id=str(uuid4())
    con=await asyncpg.connect(dsn)
    try:
        await con.execute(SCHEMA)
        await con.execute(
            """INSERT INTO dz_execution_graphs
               (goal_id,user_id,session_id,conversation_id,plan_sha256,plan,state)
               VALUES($1,$2,$3,$4,$5,$6::jsonb,'active')""",
            goal_id,user_id,session_id,conversation_id,_sha(plan),
            __import__("json").dumps(plan),
        )
    finally:
        await con.close()
    return goal_id


async def _cleanup(dsn, goal_id):
    con=await asyncpg.connect(dsn)
    try:
        await con.execute("DELETE FROM dz_execution_graph_steps WHERE goal_id=$1",goal_id)
        await con.execute("DELETE FROM dz_execution_graphs WHERE goal_id=$1",goal_id)
    finally:
        await con.close()


def _environment(dsn):
    return {
        "DRAGONZPYDER_EXECUTION_GRAPH_ENABLED":"1",
        "DRAGONZPYDER_EXECUTION_GRAPH_SCHEMA_INSTALL_ALLOWED":"1",
        "DRAGONZPYDER_PERSONAL_GOAL_TOOLS_ENABLED":"1",
        "DRAGONZPYDER_PERSONAL_MCP_SCHEDULED_ENABLED":"1",
        "DRAGONZPYDER_AGENT_DATABASE_URL":dsn,
    }


def test_real_postgres_graph_receipts_and_cross_user_isolation():
    dsn=os.environ["DRAGONZPYDER_BUDGET_TEST_DSN"]
    uid,sid,cid,other=(str(uuid4()) for _ in range(4))

    async def scenario():
        goal=await _seed(dsn,user_id=uid,session_id=sid,conversation_id=cid)
        try:
            owner=graph_tools(user_id=uid,session_id=sid,conversation_id=cid)
            outsider=graph_tools(user_id=other,session_id=sid,conversation_id=cid)
            assert (await outsider[1].ainvoke({"goal_id":goal}))["status"]=="not_found"
            assert (await owner[1].ainvoke({"goal_id":goal}))["completed_steps"]==0
            for seq in range(4):
                outcome=await execute_graph_wake(GraphWake(goal_id=goal,sequence=seq))
                assert outcome["executed"] is True
                assert outcome["sequence"]==seq
                assert outcome["state"]==("completed" if seq==3 else "active")
                duplicate=await execute_graph_wake(GraphWake(goal_id=goal,sequence=seq))
                assert duplicate["executed"] is False
            status=await owner[1].ainvoke({"goal_id":goal})
            assert status["state"]=="completed"
            assert status["completed_steps"]==4
            assert status["verified"] is True
            assert [x["tool"] for x in status["receipts"]]==[
                "operly_workflow_list","operly_tasks_list",
                "native_graph_compose","native_graph_verify"]
            assert all(r["integrity_valid"] for r in status["receipts"])
            assert "operly_workflow_list" in status["report_markdown"]
            assert "operly_tasks_list" in status["report_markdown"]
            assert (await outsider[2].ainvoke({"goal_id":goal}))["status"]=="not_cancellable"
        finally:
            await _cleanup(dsn,goal)

    with patch.dict(os.environ,_environment(dsn),clear=False), \
         patch("agent_platform.persistent_graph.require_wake_gate",
               return_value=(dsn,"service-token","agent-token","https://example.invalid/renew","https://example.invalid/run")), \
         patch("agent_platform.persistent_graph._renew",
               new=AsyncMock(return_value=("x"*50,["workflow.list","tasks.list"],"proof"*20))), \
         patch("agent_platform.operly_mcp_client.load_authorized_operly_mcp_tools",
               new=_fake_load), \
         patch("agent_platform.mcp_broker.invoke_granted_mcp_tool",
               new=_fake_invoke):
        asyncio.run(scenario())


def test_revoked_identity_blocks_pending_graph_without_receipt():
    dsn=os.environ["DRAGONZPYDER_BUDGET_TEST_DSN"]
    uid,sid,cid=(str(uuid4()) for _ in range(3))

    async def scenario():
        goal=await _seed(dsn,user_id=uid,session_id=sid,conversation_id=cid)
        try:
            result=await execute_graph_wake(GraphWake(goal_id=goal,sequence=0))
            assert result["state"]=="blocked"
            status=await graph_tools(
                user_id=uid,session_id=sid,conversation_id=cid,
            )[1].ainvoke({"goal_id":goal})
            assert status["verified"] is False
            assert status["blocked_reason"]=="authorization_revoked"
            assert status["receipts"]==[]
            replay=await execute_graph_wake(GraphWake(goal_id=goal,sequence=0))
            assert replay["executed"] is False
        finally:
            await _cleanup(dsn,goal)

    with patch.dict(os.environ,_environment(dsn),clear=False), \
         patch("agent_platform.persistent_graph.require_wake_gate",
               return_value=(dsn,"service-token","agent-token","https://example.invalid/renew","https://example.invalid/run")), \
         patch("agent_platform.persistent_graph._renew",
               new=AsyncMock(side_effect=PermissionError("revoked"))):
        asyncio.run(scenario())
