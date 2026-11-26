"""Real PostgreSQL phase receipts, artifact bytes and LangGraph restart recovery.
Model/provider responses are scripted; no external paid calls.
"""
import asyncio
import base64
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4,uuid5
import asyncpg
import pytest
from fastapi import HTTPException
from agent_platform import native_workflows as w,artifacts


def test_native_workflow_commits_and_recovers_exact_phase_without_replay(monkeypatch):
    from agent_platform import runtime
    from agent_platform.harness import build_frontier_agent
    from agent_platform.personal_bridge import personal_thread
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langchain_core.messages import AIMessage
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    dsn=os.environ["DRAGONZPYDER_BUDGET_TEST_DSN"]
    owner="workflow-test-"+uuid4().hex
    goal=uuid4()
    for key,value in {
        "DRAGONZPYDER_AGENT_ARTIFACTS_ENABLED":"1",
        "DRAGONZPYDER_ARTIFACT_KEY_B64":base64.b64encode(os.urandom(32)).decode(),
        "DRAGONZPYDER_ARTIFACT_STORAGE_BACKEND":"postgres",
        "DRAGONZPYDER_AGENT_MODEL_ID":"test/model",
        "DRAGONZPYDER_RUNTIME_ALLOWED_MODELS":"test/model",
        "DRAGONZPYDER_ADAPTIVE_ROUTING_ENABLED":"0",
        "DRAGONZPYDER_AGENT_QUICKJS_ENABLED":"0",
        "DRAGONZPYDER_AGENT_WEB_SEARCH_ENABLED":"0",
    }.items():monkeypatch.setenv(key,value)
    @asynccontextmanager
    async def db_factory():
        db=await asyncpg.connect(dsn)
        try:yield db
        finally:await db.close()
    monkeypatch.setattr(w,"_conversation_db",db_factory)
    allowed=True
    async def authority(user,session_hash):
        assert user==owner and session_hash=="synthetic-session-reference"
        if not allowed:raise PermissionError("revoked")
    monkeypatch.setattr(w,"verify_authority",authority)
    class Model(FakeMessagesListChatModel):
        def bind_tools(self,tools,**kwargs):return self
    script=Model(responses=[
        AIMessage(content="",tool_calls=[{"name":"create_text_artifact","args":{
            "name":"result.txt","content":"independent bytes","content_type":"text/plain"},"id":"write"}]),
        AIMessage(content="The input report was published."),
    ])
    model_builds=[]
    def model_client(**kwargs):
        assert kwargs["parent_job_id"]==str(goal)
        model_builds.append(kwargs)
        return script if len(model_builds)==1 else Model(responses=[
            AIMessage(content="A paid model must not be called during recovery")])
    monkeypatch.setattr(runtime,"model_client",model_client)
    plan=w.WorkflowPlan(objective="Prepare and review a report",conversation_id=uuid4(),
        request_id=uuid4(),phases=[
            w.WorkflowPhase(id="prepare",objective="Publish a text report"),
            w.WorkflowPhase(id="review",objective="Review the evidence",depends_on=["prepare"])])
    frozen=w.validate_plan(plan)
    async def run():
        async with db_factory() as db:
            root=Path(__file__).resolve().parents[1]/"agent_platform/migrations"
            await db.execute((root/"20261125_shared_artifacts.sql").read_text())
            await db.execute((root/"20261126_native_workflows.sql").read_text())
            await db.execute("""INSERT INTO dz_native_workflows
              (goal_id,owner_id,session_hash,request_id,conversation_id,plan,plan_sha256,ceiling_usd,state)
              VALUES($1,$2,$3,$4,$5,$6::jsonb,$7,0.50,'active')""",
              goal,owner,"synthetic-session-reference",plan.request_id,plan.conversation_id,
              json.dumps(frozen),w.plan_digest(frozen))
        try:
            async with AsyncPostgresSaver.from_conn_string(dsn) as saver:
                await saver.setup()
                state=SimpleNamespace(agent_runtime=SimpleNamespace(_checkpointer=saver))
                first=await w.execute_phase(goal,state)
                assert first["state"]=="active",first
                status=await w.workflow_status(owner,goal)
                report=status["phase_receipts"][0]["report"]
                assert report["artifacts"] and not report["objective_verified"]
                async with db_factory() as db:
                    _,raw=await artifacts.get(db,owner=owner,file_id=__import__("uuid").UUID(report["artifacts"][0]["id"]))
                    assert raw==b"independent bytes"
                    await db.execute("UPDATE dz_native_workflows SET state='inflight' WHERE goal_id=$1",goal)
                # Simulate process loss after an exact final checkpoint but
                # BEFORE the phase-receipt transaction. No second execution.
                run_id=uuid5(goal,"phase:1")
                prompt=w.phase_prompt(plan,plan.phases[1],[{"phase_id":"prepare",
                    "answer":report["answer"][:2000],"artifacts":report["artifacts"]}])
                graph=build_frontier_agent(Model(responses=[AIMessage(content="Reviewed the persisted report.")]),saver)
                await graph.ainvoke({"messages":[{"role":"user","content":prompt,"id":str(run_id)}]},
                    config={"configurable":{"thread_id":personal_thread(owner,str(run_id))},"recursion_limit":128})
            # New PostgreSQL saver and graph; recovery cannot rely on memory.
            async with AsyncPostgresSaver.from_conn_string(dsn) as saver2:
                state=SimpleNamespace(agent_runtime=SimpleNamespace(_checkpointer=saver2))
                result=await w.execute_phase(goal,state)
                assert result["state"]=="completed",result
                assert await w.execute_phase(goal,state)=={"goal_id":str(goal),"state":"completed"}
                status=await w.workflow_status(owner,goal)
                assert status["completed_phases"]==2
                assert status["phase_receipts"][1]["report"]["recovered_checkpoint"] is True
                assert status["phase_receipts"][1]["report"]["answer"]=="Reviewed the persisted report."
                with pytest.raises(HTTPException) as denied:
                    await w.workflow_status(owner+"-other",goal)
                assert denied.value.status_code==404
                assert len(model_builds)==2
        finally:
            async with db_factory() as db:
                await db.execute("DELETE FROM dz_native_workflow_phases WHERE goal_id=$1",goal)
                await db.execute("DELETE FROM dz_native_workflows WHERE goal_id=$1",goal)
                await db.execute("DELETE FROM dz_agent_artifacts WHERE owner_id=$1",owner)
    asyncio.run(run())
