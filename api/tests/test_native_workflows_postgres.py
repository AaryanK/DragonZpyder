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


def test_media_graph_selected_image_and_generation_real_postgres(monkeypatch):
    import httpx
    from uuid import UUID
    from agent_platform.media_tools import MediaRun
    from agent_platform.harness import build_frontier_agent
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langchain_core.messages import AIMessage,ToolMessage
    from langgraph.checkpoint.memory import MemorySaver
    dsn=os.environ["DRAGONZPYDER_BUDGET_TEST_DSN"]
    owner="media-test-"+uuid4().hex
    rid=uuid4()
    raw=base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jVZkAAAAASUVORK5CYII=")
    for key,value in {
        "DRAGONZPYDER_AGENT_ARTIFACTS_ENABLED":"1",
        "DRAGONZPYDER_ARTIFACT_KEY_B64":base64.b64encode(os.urandom(32)).decode(),
        "DRAGONZPYDER_ARTIFACT_STORAGE_BACKEND":"postgres",
        "DRAGONZPYDER_AGENT_MEDIA_ENABLED":"1",
        "DRAGONZPYDER_AGENT_USE_GATEWAY":"1",
        "DRAGONZPYDER_AGENT_GATEWAY_BASE_URL":"https://gateway.example.org/internal/agent/v1",
        "DRAGONZPYDER_AGENT_GATEWAY_TOKEN":"synthetic-service-token-"+"x"*40,
        "DRAGONZPYDER_AGENT_VISION_MODEL":"test/vision",
        "DRAGONZPYDER_AGENT_IMAGE_MODEL":"test/image",
        "DRAGONZPYDER_AGENT_QUICKJS_ENABLED":"0",
        "DRAGONZPYDER_AGENT_WEB_SEARCH_ENABLED":"0",
    }.items():monkeypatch.setenv(key,value)
    for key in ("DRAGONZPYDER_AGENT_TRANSCRIPTION_MODEL","DRAGONZPYDER_AGENT_SPEECH_MODEL"):
        monkeypatch.delenv(key,raising=False)
    @asynccontextmanager
    async def db_factory():
        db=await asyncpg.connect(dsn)
        try:yield db
        finally:await db.close()
    calls=[]
    def provider(req):
        assert req.headers["authorization"].startswith("Bearer synthetic-service-token-")
        body=json.loads(req.content)
        calls.append(body["model"])
        headers={"x-dragonzpyder-audit":"persisted","x-dragonzpyder-request-id":str(uuid4()),
                 "x-dragonzpyder-trace-id":uuid4().hex}
        if body["model"]=="test/vision":
            assert body["messages"][0]["content"][1]["image_url"]["url"]=="data:image/png;base64,"+base64.b64encode(raw).decode()
            return httpx.Response(200,json={"choices":[{"message":{"content":"A tiny image."}}]},headers=headers)
        assert body=={"model":"test/image","prompt":"Draw a small dot","n":1}
        return httpx.Response(200,json={"data":[{"b64_json":base64.b64encode(raw).decode()}]},headers=headers)
    async def authorize():return None
    class Model(FakeMessagesListChatModel):
        def bind_tools(self,tools,**kwargs):return self
    async def run():
        async with db_factory() as db:
            root=Path(__file__).resolve().parents[1]/"agent_platform/migrations"
            await db.execute((root/"20261125_shared_artifacts.sql").read_text())
            await db.execute((root/"20261126_agent_media_attempts.sql").read_text())
            info=await artifacts.put(db,owner=owner,name="input.png",mime="image/png",data=raw)
        try:
            async with httpx.AsyncClient(transport=httpx.MockTransport(provider)) as http:
                binding=MediaRun(owner=owner,run_id=rid,allowed_ids=[UUID(info["id"])],
                    db_factory=db_factory,authorize=authorize,http=http)
                with pytest.raises(PermissionError):await binding.selected(str(uuid4()))
                model=Model(responses=[
                    AIMessage(content="",tool_calls=[{"name":"inspect_image","args":{"file_id":info["id"],"question":"Describe"},"id":"vision"}]),
                    AIMessage(content="",tool_calls=[{"name":"generate_image","args":{"prompt":"Draw a small dot"},"id":"image"}]),
                    AIMessage(content="Image inspected and generated."),
                ])
                agent=build_frontier_agent(model,MemorySaver(),media_run=binding)
                state=await agent.ainvoke({"messages":[{"role":"user","content":"Inspect and generate a similar image"}]},
                    config={"configurable":{"thread_id":"media-"+rid.hex},"recursion_limit":128})
                responses=[m for m in state["messages"] if isinstance(m,ToolMessage)]
                assert len(responses)==2 and all(m.status=="success" for m in responses)
                assert "A tiny image." in str(responses[0].content)
                assert base64.b64encode(raw).decode() not in str(responses)
                assert "synthetic-service-token" not in str(state)
                async with db_factory() as db:
                    row=await db.fetchrow("SELECT id FROM dz_agent_artifacts WHERE owner_id=$1 AND run_id=$2",owner,rid)
                    _,stored=await artifacts.get(db,owner=owner,file_id=row["id"])
                    assert stored==raw
                    assert await db.fetchval("SELECT count(*) FROM dz_agent_media_attempts WHERE owner_id=$1 AND run_id=$2 AND state='returned'",owner,rid)==2
                with pytest.raises(PermissionError):
                    await binding.invoke("image",{"prompt":"Draw a small dot","n":1})
                assert calls==["test/vision","test/image"]
        finally:
            async with db_factory() as db:
                await db.execute("DELETE FROM dz_agent_media_attempts WHERE owner_id=$1",owner)
                await db.execute("DELETE FROM dz_agent_artifacts WHERE owner_id=$1",owner)
    asyncio.run(run())
