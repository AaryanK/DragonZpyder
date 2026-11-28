"""Offline tests for the new native harness surfaces, never live acceptance."""
import asyncio
import base64
from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import uuid4,uuid5
import pytest
from fastapi import HTTPException


def test_adaptive_routing_conservative_model_selection():
    from agent_platform.adaptive_routing import choose_route
    kw=dict(default_model="standard",cheap_model="fast",reasoning_model="reasoning",
            approved_models=frozenset({"standard","fast","reasoning"}))
    assert choose_route(objective="Hello!",**kw).model=="fast"
    assert choose_route(objective="hello",has_tools=True,**kw).model=="standard"
    assert choose_route(objective="Analyze this",**kw).model=="reasoning"
    assert choose_route(objective="Hello",has_attachments=True,**kw).model=="reasoning"
    assert choose_route(objective="hello",durable=True,**kw).model=="reasoning"
    assert choose_route(objective="hello",tool_failures=2,**kw).model=="reasoning"
    assert choose_route(objective="hello",**dict(kw,cheap_model="unapproved")).model=="standard"


def test_model_escalation_uses_same_graph_after_two_observed_failures(monkeypatch):
    from agent_platform.adaptive_routing import recovery_middleware
    from agent_platform.harness import build_frontier_agent
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langchain_core.messages import AIMessage
    from langchain_core.tools import tool,ToolException
    from langgraph.checkpoint.memory import MemorySaver
    class Model(FakeMessagesListChatModel):
        def bind_tools(self,tools,**kw):return self
    calls=[]
    @tool
    async def lookup(query:str)->str:
        """Read a synthetic record."""
        calls.append(query)
        raise ToolException("Synthetic lookup failed")
    lookup.handle_tool_error=True
    cheap=Model(responses=[
        AIMessage(content="",tool_calls=[{"name":"lookup","args":{"query":"a"},"id":"one"}]),
        AIMessage(content="",tool_calls=[{"name":"lookup","args":{"query":"b"},"id":"two"}]),
        AIMessage(content="Wrong model: should have escalated"),
    ])
    strong=Model(responses=[AIMessage(content="The two reads failed; no result verified.")])
    monkeypatch.setenv("DRAGONZPYDER_SYNTHETIC_TOOLS_ENABLED","1")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_WEB_SEARCH_ENABLED","0")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_QUICKJS_ENABLED","0")
    async def run():
        agent=build_frontier_agent(cheap,MemorySaver(),synthetic_tools=[lookup],
            routing_middleware=recovery_middleware(initial_model=cheap,reasoning_model=strong))
        out=await agent.ainvoke({"messages":[{"role":"user","content":"Check the record"}]},
            config={"configurable":{"thread_id":"routing-test"},"recursion_limit":128})
        assert calls==["a","b"]
        assert out["messages"][-1].content=="The two reads failed; no result verified."
    asyncio.run(run())


def test_reviewed_media_policy_rejects_remote_urls_and_wrong_modalities(monkeypatch):
    from agent_platform.media_policy import validate_media_payload
    monkeypatch.setenv("DRAGONZPYDER_AGENT_VISION_MODEL","test/vision")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_IMAGE_MODEL","test/image")
    raw=b"\x89PNG\r\n\x1a\n"+b"x"*32
    data="data:image/png;base64,"+base64.b64encode(raw).decode()
    payload={"model":"test/vision","messages":[{"role":"user","content":[
        {"type":"text","text":"Describe"},
        {"type":"image_url","image_url":{"url":data}}]}],"max_tokens":768}
    assert validate_media_payload("/chat/completions",payload)=="vision"
    payload["messages"][0]["content"][1]["image_url"]["url"]="https://example.com/private"
    with pytest.raises(ValueError):validate_media_payload("/chat/completions",payload)
    with pytest.raises(ValueError):validate_media_payload("/images",{"model":"test/vision","prompt":"draw","n":1})
    with pytest.raises(ValueError):validate_media_payload("/images",{"model":"test/image","prompt":"draw","n":2})


def test_native_voice_turn_is_bound_to_session_and_exact_event(monkeypatch):
    from agent_platform import first_party_voice as voice
    from agent_platform.first_party_chat import _fingerprint
    sid,cid=uuid4(),uuid4()
    calls=[]
    class DB:
        saved=None
        active=True
        async def fetchval(self,*a):return True
        async def fetchrow(self,sql,*args):
            if "FROM dz_native_voice_sessions" in sql:
                return {"conversation_id":cid,"mcp_connection_ids":[]} if self.active and args==("owner",sid) else None
            return self.saved
        async def execute(self,*a):pass
    db=DB()
    @asynccontextmanager
    async def connection():yield db
    async def owner(request,changing):return "owner"
    async def chat(payload,request,user):
        calls.append(payload)
        result={"conversation_id":str(cid),"message":"Actual core response","status":"completed"}
        db.saved={"conversation_id":cid,"status":"completed","response":result,"fingerprint":_fingerprint(payload)}
        return result
    monkeypatch.setattr(voice,"_owner",owner)
    monkeypatch.setattr(voice,"_conversation_db",connection)
    monkeypatch.setattr(voice,"_chat_owned",chat)
    monkeypatch.setattr(voice,"voice_agent_enabled",lambda:True)
    async def run():
        data=voice.VoiceTurn(event_id="item_123",transcript="Read the selected record")
        one=await voice.turn(sid,data,None)
        assert one["message"]=="Actual core response"
        assert calls[0].request_id==uuid5(sid,"item_123")
        assert await voice.turn(sid,data,None)==one and len(calls)==1
        with pytest.raises(HTTPException) as exc:
            await voice.turn(sid,voice.VoiceTurn(event_id="item_123",transcript="Changed"),None)
        assert exc.value.status_code==409
        db.active=False
        with pytest.raises(HTTPException) as exc:
            await voice.turn(sid,data,None)
        assert exc.value.status_code==404 and len(calls)==1
    asyncio.run(run())


def test_generic_workflow_plan_forward_dependencies_and_no_extra_authority():
    from agent_platform.native_workflows import WorkflowPlan,WorkflowPhase,validate_plan
    from pydantic import ValidationError
    fields=dict(objective="Research and synthesize",conversation_id=uuid4(),request_id=uuid4())
    a=WorkflowPhase(id="research",objective="Find and compare sources")
    b=WorkflowPhase(id="synthesis",objective="Publish an evidence report",depends_on=["research"])
    assert len(validate_plan(WorkflowPlan(**fields,phases=[a,b]))["phases"])==2
    for phases in ([b,a],[a,a]):
        with pytest.raises(ValueError):validate_plan(WorkflowPlan(**fields,phases=phases))
    with pytest.raises(ValidationError):
        WorkflowPlan(**fields,phases=[a],owner_id="attacker")


def test_native_control_unknown_outcome_stops_next_agent_step():
    from langchain_core.messages import ToolMessage
    from agent_platform.tool_outcomes import tool_outcome, unresolved_external_control
    for name, payload in [
        ("schedule_workflow", '{"state":"uncertain","objective_verified":false}'),
        ("generate_image", '{"status":"outcome_unconfirmed","objective_verified":false}'),
    ]:
        msg = ToolMessage(content=payload, name=name, tool_call_id="test-call")
        assert tool_outcome(msg) == "unknown"
        assert unresolved_external_control([msg]) == "external_outcome_unconfirmed"
    receipt = ToolMessage(content='{"state":"scheduled","objective_verified":false}',
                          name="schedule_workflow",tool_call_id="test-schedule")
    assert unresolved_external_control([receipt]) is None


def test_workspace_handoff_is_bounded_and_does_not_copy_other_state():
    import json
    from agent_platform.native_workflows import workspace_bytes
    files={"/workspace/report.md":{"content":["original"],"created_at":"t","modified_at":"t"},
           "/large_tool_results/raw":{"content":["not part of working directory"]},
           "/workspace/../private":{"content":["invalid path"]}}
    raw,paths=workspace_bytes(files)
    assert paths==["/workspace/report.md"]
    assert json.loads(raw)=={paths[0]:files[paths[0]]}
    with pytest.raises(ValueError):
        workspace_bytes({"/workspace/report.md":{"content":["x"*(512*1024+1)]}})
    with pytest.raises(ValueError):
        workspace_bytes({"/workspace/report.md":{"content":42}})
    raw,_=workspace_bytes({"/workspace/report.md":{"content":"current SDK","encoding":"utf-8"}})
    assert json.loads(raw)["/workspace/report.md"]["content"]=="current SDK"


def test_required_reads_are_evidence_not_model_claims():
    from langchain_core.messages import AIMessage,ToolMessage
    from agent_platform.native_workflows import required_reads_observed
    from agent_platform.tool_outcomes import tool_outcome
    path="/workspace/report.md"
    call=AIMessage(content="",tool_calls=[{"id":"read","name":"read_file","args":{"file_path":path}}])
    for failure in ("Error: File not found","No files found","Permission denied"):
        msg=ToolMessage(name="read_file",tool_call_id="read",content=failure,status="success")
        assert tool_outcome(msg)=="failed"
        assert not required_reads_observed([call,msg,AIMessage(content="I read it.")],[path])
    assert not required_reads_observed([AIMessage(content="I read it.")],[path])
    success=ToolMessage(name="read_file",tool_call_id="read",content="1\tOriginal report",status="success")
    assert required_reads_observed([call,success],[path])
    assert not required_reads_observed([call,success],["/workspace/other.md"])


def test_new_workflow_contract_requires_checkable_outputs():
    from agent_platform.native_workflows import WorkflowPhase,WorkflowPlan,require_acceptance,objective_id
    fields=dict(objective="Produce an evidence report",conversation_id=uuid4(),request_id=uuid4())
    with pytest.raises(ValueError):
        require_acceptance(WorkflowPlan(**fields,phases=[WorkflowPhase(id="verify",objective="Trust me")]))
    require_acceptance(WorkflowPlan(**fields,phases=[WorkflowPhase(id="verify",objective="Publish",required_artifact_names=["report.md"])]))
    require_acceptance(WorkflowPlan(**fields,phases=[WorkflowPhase(id="verify",objective="Return exact text",expected_answer="42")]))
    assert objective_id("owner-a",fields["request_id"])==objective_id("owner-a",fields["request_id"])
    assert objective_id("owner-a",fields["request_id"])!=objective_id("owner-b",fields["request_id"])


def test_origin_budget_is_admitted_before_work(monkeypatch):
    from agent_platform import native_workflows as w
    events=[]
    req=uuid4()
    monkeypatch.setattr(w,"require_gate",lambda:"0.50")
    async def verify(owner,session_hash):
        events.append(("authority",owner,session_hash))
    async def create(goal_id,ceiling,http):
        events.append(("budget",goal_id,ceiling))
    monkeypatch.setattr(w,"verify_authority",verify)
    monkeypatch.setattr(w,"create_budget",create)
    goal,ceiling=asyncio.run(w.admit_origin(owner="owner-a",request_id=req,session_hash="synthetic",http=None))
    assert goal==w.objective_id("owner-a",req) and ceiling=="0.50"
    assert events==[("authority","owner-a","synthetic"),("budget",goal,"0.50")]
