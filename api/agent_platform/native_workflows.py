"""Native Personal durable objectives, dispatched by Hatchet.

One canonical Deep Agents harness per phase, one immutable goal budget, a
durable PostgreSQL cursor, exact checkpoint recovery, and live first-party
identity on every wake. Hatchet carries opaque IDs only. No Operly dependency,
external mutations, hidden scheduling, or automatic replay of an uncertain turn.
"""
from __future__ import annotations

import asyncio
from datetime import datetime,timedelta,timezone
import hashlib
import hmac
import json
import os
import re
from urllib.parse import urlsplit
from uuid import UUID,uuid4,uuid5

import httpx
from fastapi import APIRouter,HTTPException,Request
from pydantic import BaseModel,ConfigDict,Field

from .first_party_chat import _owner,_conversation_db,_require_conversation
from .budget_reservations import amount

router=APIRouter(tags=["native-durable-workflows"])
MAX_STEPS=6


class WorkflowPhase(BaseModel):
    model_config=ConfigDict(extra="forbid")
    id:str=Field(pattern=r"^[a-z][a-z0-9_]{0,39}$")
    objective:str=Field(min_length=1,max_length=2000)
    depends_on:list[str]=Field(default_factory=list,max_length=5)


class WorkflowPlan(BaseModel):
    model_config=ConfigDict(extra="forbid")
    objective:str=Field(min_length=1,max_length=4000)
    phases:list[WorkflowPhase]=Field(min_length=1,max_length=MAX_STEPS)
    start_after_minutes:int=Field(default=1,ge=1,le=1440,strict=True)
    conversation_id:UUID
    request_id:UUID
    attachment_ids:list[UUID]=Field(default_factory=list,max_length=5)
    mcp_connection_ids:list[str]=Field(default_factory=list,max_length=10)
    allow_computer:bool=Field(default=False,strict=True)


class WorkflowWake(BaseModel):
    model_config=ConfigDict(extra="forbid")
    goal_id:UUID


def plan_digest(plan):
    return hashlib.sha256(json.dumps(plan,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()


def validate_plan(plan:WorkflowPlan):
    seen=set()
    for phase in plan.phases:
        if (phase.id in seen or not phase.objective.strip() or
                len(set(phase.depends_on))!=len(phase.depends_on) or
                not set(phase.depends_on)<=seen):
            raise ValueError("Invalid forward dependencies")
        seen.add(phase.id)
    if not plan.objective.strip() or len(set(plan.attachment_ids))!=len(plan.attachment_ids):
        raise ValueError("Invalid objective or attachment selection")
    if (len(set(plan.mcp_connection_ids))!=len(plan.mcp_connection_ids)
            or any(not re.fullmatch(r"c[a-f0-9]{30}",x) for x in plan.mcp_connection_ids)):
        raise ValueError("Invalid account selection")
    return plan.model_dump(mode="json")


def enabled():
    return all(os.getenv(x)=="1" for x in (
        "DRAGONZPYDER_NATIVE_DURABLE_WORKFLOWS_ENABLED",
        "DRAGONZPYDER_AGENT_USE_GATEWAY",
        "DRAGONZPYDER_AGENT_PARALLEL_GATEWAY_ENABLED",
        "DRAGONZPYDER_AGENT_ARTIFACTS_ENABLED"))


def require_gate():
    if not enabled() or not os.getenv("HATCHET_CLIENT_TOKEN"):
        raise RuntimeError("Durable workflow admission unavailable")
    ceiling=amount(os.environ["DRAGONZPYDER_NATIVE_DURABLE_MAX_USD"])
    if ceiling>amount("0.50"):
        raise ValueError("Workflow exceeds approved initial provider cap")
    return str(ceiling)


def as_json(value):
    return json.loads(value) if isinstance(value,str) else value


async def verify_authority(owner,session_hash):
    from identity.http_bridge import _identity_db
    # A keyed digest is a lookup reference, not an API bearer credential.
    async with _identity_db() as db:
        active=await db.fetchval("""SELECT EXISTS(SELECT 1 FROM identity_browser_sessions s
            JOIN identity_accounts a ON a.subject=s.subject
            WHERE s.session_hash=$1 AND s.subject=$2 AND s.revoked_at IS NULL
            AND s.expires_at>now() AND a.status='active' AND a.source_active=TRUE)""",
            session_hash,owner)
    if active is not True:
        raise PermissionError("Original workflow authority expired or revoked")


async def create_budget(goal_id,ceiling,http):
    base=os.getenv("DRAGONZPYDER_AGENT_GATEWAY_BASE_URL","").rstrip("/")
    p=urlsplit(base)
    token=os.getenv("DRAGONZPYDER_AGENT_GATEWAY_TOKEN","")
    if ((p.scheme!="https" and not (p.scheme=="http" and p.hostname and
          p.hostname.endswith(".railway.internal"))) or not p.hostname
          or p.username or p.password or p.query or p.fragment
          or not p.path.endswith("/internal/agent/v1") or len(token)<32):
        raise ValueError("Metered gateway unavailable")
    response=await http.post(base+"/parallel-budget",json={"job_id":str(goal_id),"ceiling_usd":ceiling},
        headers={"Authorization":"Bearer "+token},timeout=20,follow_redirects=False)
    if response.status_code!=200 or len(response.content)>4000:
        raise RuntimeError("Parent budget not confirmed")
    result=response.json()
    if result.get("job_id")!=str(goal_id) or result.get("atomic_gateway_enforced") is not True:
        raise RuntimeError("Parent budget evidence missing")


async def schedule(*,owner,session_hash,plan,http):
    ceiling=require_gate()
    frozen=validate_plan(plan)
    await verify_authority(owner,session_hash)
    from . import artifacts
    async with _conversation_db() as db:
        await _require_conversation(db,user=owner,conversation_id=plan.conversation_id)
        await artifacts.describe(db,owner=owner,ids=plan.attachment_ids)
        async with db.transaction():
            await db.execute("SELECT pg_advisory_xact_lock(hashtextextended($1,0))","dz-durable:"+owner)
            existing=await db.fetchrow("""SELECT goal_id,plan_sha256,state FROM dz_native_workflows
                WHERE owner_id=$1 AND request_id=$2""",owner,plan.request_id)
            if existing:
                if existing["plan_sha256"]!=plan_digest(frozen):
                    raise HTTPException(409,"Workflow request identity conflict")
                return {"goal_id":str(existing["goal_id"]),"state":existing["state"],
                        "objective_verified":False}
            count=await db.fetchval("""SELECT count(*) FROM dz_native_workflows
                WHERE owner_id=$1 AND state IN ('preparing','active','inflight','uncertain')""",owner)
            if count>=2:
                raise HTTPException(429,"Active workflow allowance exhausted")
            goal_id=uuid4()
            await db.execute("""INSERT INTO dz_native_workflows
                (goal_id,owner_id,session_hash,request_id,conversation_id,plan,plan_sha256,
                 ceiling_usd,state) VALUES($1,$2,$3,$4,$5,$6::jsonb,$7,$8,'preparing')""",
                goal_id,owner,session_hash,plan.request_id,plan.conversation_id,
                json.dumps(frozen),plan_digest(frozen),amount(ceiling))
    try:
        await create_budget(goal_id,ceiling,http)
        from hatchet_sdk import Hatchet
        task=make_native_workflow_task(Hatchet())
        await task.aio_schedule(run_at=datetime.now(timezone.utc)+timedelta(minutes=plan.start_after_minutes),
                                input=WorkflowWake(goal_id=goal_id))
        async with _conversation_db() as db:
            updated=await db.fetchval("""UPDATE dz_native_workflows SET state='active',updated_at=now()
                WHERE goal_id=$1 AND state='preparing' RETURNING goal_id""",goal_id)
            if updated!=goal_id:
                raise RuntimeError("Workflow dispatch not committed")
    except Exception:
        async with _conversation_db() as db:
            await db.execute("""UPDATE dz_native_workflows SET state='uncertain',updated_at=now()
                WHERE goal_id=$1 AND state='preparing'""",goal_id)
        return {"goal_id":str(goal_id),"state":"uncertain","objective_verified":False}
    return {"goal_id":str(goal_id),"state":"scheduled","phases":len(plan.phases),
            "objective_verified":False}


def session_reference(request):
    from identity.grants import _secret_digest
    secret=request.cookies.get("__Host-dz_identity","")
    if not isinstance(secret,str) or not 20<=len(secret)<=128:
        raise PermissionError("Authenticated browser session required")
    return _secret_digest(secret)


@router.post("/v2/personal/workflows")
async def create_workflow(plan:WorkflowPlan,request:Request):
    owner=await _owner(request,changing=True)
    if not enabled():
        raise HTTPException(503,"Durable workflows unavailable")
    try:
        return await schedule(owner=owner,session_hash=session_reference(request),plan=plan,http=request.app.state.http)
    except (ValueError,RuntimeError,KeyError,PermissionError):
        raise HTTPException(422,"Workflow plan, authority or budget unavailable") from None


async def workflow_status(owner,goal_id):
    async with _conversation_db() as db:
        row=await db.fetchrow("""SELECT goal_id,state,next_sequence,plan,blocked_reason,updated_at
            FROM dz_native_workflows WHERE owner_id=$1 AND goal_id=$2""",owner,goal_id)
        if row is None:
            raise HTTPException(404,"Workflow not found")
        phases=await db.fetch("""SELECT sequence,phase_id,report,report_sha256
            FROM dz_native_workflow_phases WHERE goal_id=$1 ORDER BY sequence""",goal_id)
    results=[]
    for item in phases:
        report=as_json(item["report"])
        if plan_digest(report)!=item["report_sha256"]:
            raise HTTPException(503,"Workflow receipt integrity failure")
        results.append({"sequence":item["sequence"],"phase_id":item["phase_id"],"report":report})
    return {"goal_id":str(goal_id),"state":row["state"],"completed_phases":row["next_sequence"],
            "total_phases":len(as_json(row["plan"])["phases"]),"blocked_reason":row["blocked_reason"],
            "phase_receipts":results,"objective_verified":False}


@router.get("/v2/personal/workflows/{goal_id}")
async def status(goal_id:UUID,request:Request):
    return await workflow_status(await _owner(request,changing=False),goal_id)


async def cancel_workflow(owner,goal_id):
    async with _conversation_db() as db:
        row=await db.fetchval("""UPDATE dz_native_workflows SET cancel_requested=TRUE,
            state=CASE WHEN state='inflight' THEN state ELSE 'cancelled' END,updated_at=now()
            WHERE owner_id=$1 AND goal_id=$2 AND state IN ('preparing','active','inflight')
            RETURNING state""",owner,goal_id)
    return {"goal_id":str(goal_id),"state":row or "not_cancellable","cancel_requested":row is not None}


@router.post("/v2/personal/workflows/{goal_id}/cancel")
async def cancel(goal_id:UUID,request:Request):
    return await cancel_workflow(await _owner(request,changing=True),goal_id)


def native_workflow_tools(*,owner,session_hash,conversation_id,request_id,
                          attachment_ids,mcp_connection_ids,allow_computer,http):
    from langchain_core.tools import tool,ToolException

    @tool
    async def schedule_workflow(objective:str,phases:list[WorkflowPhase],start_after_minutes:int=1)->dict:
        """Schedule an explicitly requested finite workflow of up to six natural-language phases.
        Each phase has id, objective and earlier dependencies. Scheduling is not completion.
        No external mutations or unattended media generation. Use selected reviewed read capabilities,
        authorized compute if granted, and publish artifacts for later phases."""
        try:
            plan=WorkflowPlan(objective=objective,phases=phases,start_after_minutes=start_after_minutes,
                conversation_id=conversation_id,request_id=request_id,attachment_ids=attachment_ids,
                mcp_connection_ids=mcp_connection_ids,allow_computer=allow_computer)
            return await schedule(owner=owner,session_hash=session_hash,plan=plan,http=http)
        except Exception:
            raise ToolException("Workflow schedule unavailable or unconfirmed; do not replay") from None

    @tool
    async def inspect_workflow(goal_id:str)->dict:
        """Inspect actual persisted phase receipts for an owned workflow."""
        try:return await workflow_status(owner,UUID(goal_id))
        except Exception:raise ToolException("Workflow status unavailable") from None

    @tool
    async def stop_workflow(goal_id:str)->dict:
        """Request cancellation of an owned workflow. Already dispatched operations may need reconciliation."""
        try:return await cancel_workflow(owner,UUID(goal_id))
        except Exception:raise ToolException("Workflow cancellation unavailable") from None

    for t in (schedule_workflow,inspect_workflow,stop_workflow):t.handle_tool_error=True
    return [schedule_workflow,inspect_workflow,stop_workflow]


def _worker_endpoint():
    endpoint=os.getenv("DRAGONZPYDER_NATIVE_DURABLE_WAKE_URL","")
    p=urlsplit(endpoint)
    token=os.getenv("DRAGONZPYDER_NATIVE_DURABLE_WORKER_TOKEN","")
    if (not (p.scheme=="https" and p.hostname=="api.dragonzpyder.xyz" or
             p.scheme=="http" and p.hostname and p.hostname.endswith(".railway.internal"))
            or p.path!="/internal/agents/native-workflow/wake" or p.query or p.fragment
            or p.username or p.password or len(token)<40):
        raise RuntimeError("Private workflow worker endpoint unavailable")
    return endpoint,token


def make_native_workflow_task(hatchet):
    @hatchet.task(name="dragonzpyder-native-workflow",input_validator=WorkflowWake,
                  concurrency=2,retries=2,execution_timeout=timedelta(minutes=18))
    async def run(input:WorkflowWake,ctx)->dict:
        endpoint,token=_worker_endpoint()
        async with httpx.AsyncClient(trust_env=False,follow_redirects=False) as http:
            for _ in range(MAX_STEPS+1):
                response=await http.post(endpoint,json={"goal_id":str(input.goal_id)},
                    headers={"Authorization":"Bearer "+token},timeout=220)
                if response.status_code!=200 or len(response.content)>16000:
                    raise RuntimeError("Workflow wake outcome unavailable")
                result=response.json()
                if result.get("state")!="active":
                    return result
        raise RuntimeError("Workflow exceeded phase bound")
    return run


@router.post("/internal/agents/native-workflow/wake")
async def wake(payload:WorkflowWake,request:Request):
    token=os.getenv("DRAGONZPYDER_NATIVE_DURABLE_WORKER_TOKEN","")
    bearer=request.headers.get("authorization","")
    if len(token)<40 or not hmac.compare_digest(bearer,"Bearer "+token):
        raise HTTPException(403,"Dedicated workflow worker required")
    require_gate()
    return await execute_phase(payload.goal_id,request.app.state)
