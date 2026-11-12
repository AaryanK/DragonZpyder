"""Offline gateway parent reservation and parallel fan-out contracts."""
import asyncio
from decimal import Decimal
from uuid import uuid4

import pytest
from agent_platform.gateway_parent_budget import (
    ParentBudgetGateway, audited_provider_cost, conservative_request_ceiling,
)
from agent_platform.budget_reservations import BudgetExceeded


def test_conservative_request_price_bound_and_id_validation():
    assert Decimal(conservative_request_ceiling(
        payload_bytes=160000, output_tokens=4096)) > Decimal("0.176")
    assert Decimal(conservative_request_ceiling(
        payload_bytes=2000, output_tokens=768)) < Decimal("0.006")
    for args in ((0,100), (160001,100), (100,0), (100,4097)):
        with pytest.raises(ValueError):
            conservative_request_ceiling(
                payload_bytes=args[0], output_tokens=args[1])


@pytest.mark.parametrize(("report","expected"),[
    ({"usage":{"cost":0.00123}},"0.0012300000"),
    ({"usage":{"cost":"0"}},"0"),
    ({"usage":{"cost":None}},None),
    ({"usage":{"cost":"NaN"}},None),
    ({"usage":{}},None),({},None),
])
def test_unknown_usage_never_becomes_zero(report,expected):
    assert audited_provider_cost(report)==expected


def test_parent_gateway_reserves_before_inference_and_unknown_cost_stays_held():
    class FakeStore:
        def __init__(self):
            self.calls=[]
        async def create_job(self,**kwargs):
            self.calls.append(("create",kwargs))
        async def reserve(self,**kwargs):
            self.calls.append(("reserve",kwargs))
            return True
        async def settle(self,**kwargs):
            self.calls.append(("settle",kwargs))
            if kwargs["actual_usd"] is None:
                raise BudgetExceeded("Unknown; retain hold")
            return True
    async def exercise():
        gateway=ParentBudgetGateway()
        gateway.store=FakeStore()
        job,request=str(uuid4()),str(uuid4())
        await gateway.create(job_id=job,ceiling_usd="0.15")
        estimate=await gateway.reserve(
            job_id=job,request_id=request,payload_bytes=2500,
            output_tokens=1200)
        assert Decimal(estimate)>0
        assert not await gateway.settle(job_id=job,request_id=request,
                                         provider_response={"usage":{}})
        calls=gateway.store.calls
        assert [c[0] for c in calls]==["create","reserve","settle"]
        assert calls[-1][1]["actual_usd"] is None
    asyncio.run(exercise())


def test_parent_budget_without_gateway_fails_closed():
    gateway=ParentBudgetGateway()
    async def exercise():
        with pytest.raises(BudgetExceeded):
            await gateway.create(job_id=str(uuid4()),ceiling_usd="0.10")
        with pytest.raises(BudgetExceeded):
            await gateway.reserve(job_id=str(uuid4()),
                request_id=str(uuid4()),payload_bytes=100,
                output_tokens=100)
    asyncio.run(exercise())


def test_gated_paid_parallel_tracks_share_one_parent_job_offline(monkeypatch):
    from agent_platform import runtime
    for k in (
        "DRAGONZPYDER_AGENT_PARALLEL_EVAL_ENABLED",
        "DRAGONZPYDER_AGENT_STRESS_EVAL_ENABLED",
        "DRAGONZPYDER_AGENT_EVAL_ALLOW_PAID",
        "DRAGONZPYDER_AGENT_USE_GATEWAY",
        "DRAGONZPYDER_AGENT_PRODUCTION_MODE",
        "DRAGONZPYDER_AGENT_HARNESS_V2",
        "DRAGONZPYDER_AGENT_PARALLEL_GATEWAY_ENABLED",
    ):
        monkeypatch.setenv(k,"1")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_GATEWAY_BASE_URL",
        "http://dragonzpyder-gateway.railway.internal:8080/internal/agent/v1")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_GATEWAY_TOKEN","x"*48)
    monkeypatch.setenv("DRAGONZPYDER_AGENT_PARALLEL_PARENT_CEILING_USD","0.10")
    jobs=[]
    class Client:
        def __init__(self,**kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
        async def post(self,url,*,headers,json):
            jobs.append(json["job_id"])
            assert headers["Authorization"]=="Bearer "+"x"*48
            class Response:
                status_code=200
            return Response()
    monkeypatch.setattr(runtime.httpx,"AsyncClient",Client)
    children=[]
    async def fake_run_report(self,**kwargs):
        children.append(kwargs["parent_job_id"])
        await asyncio.sleep(0.02)
        return {"answer":"Synthetic offline track",
                "virtual_artifact_paths":[],
                "successful_tools":[],
                "objective_verified":False}
    monkeypatch.setattr(runtime.AgentRuntime,"run_report",fake_run_report)
    runner=runtime.AgentRuntime()
    runner._checkpointer=object()
    result=asyncio.run(runner.run_parallel_report(
        service_id="staging",thread_id="parent-test",
        tracks=[{"id":"a","prompt":"synthetic a"},
                {"id":"b","prompt":"synthetic b"}]))
    assert len(jobs)==1
    assert children==[jobs[0]]*2
    assert result["parallelism_observed"] is True
    assert result["objective_verified"] is False
    assert result["budget_ceiling_usd"]=="0.1000000000"


def test_model_client_attaches_parent_header_only_when_gated(monkeypatch):
    from agent_platform import runtime
    monkeypatch.setenv("DRAGONZPYDER_AGENT_PARALLEL_GATEWAY_ENABLED","1")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_USE_GATEWAY","1")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_GATEWAY_TOKEN","t"*44)
    monkeypatch.setenv("DRAGONZPYDER_AGENT_GATEWAY_BASE_URL",
        "https://gateway.example/internal/agent/v1")
    monkeypatch.setenv("DRAGONZPYDER_RUNTIME_ALLOWED_MODELS","openai/gpt-oss-120b")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_MODEL_ID","openai/gpt-oss-120b")
    captured={}
    monkeypatch.setattr(runtime,"ChatOpenAI",lambda **kw:captured.update(kw) or object())
    job=str(uuid4())
    runtime.model_client(parent_job_id=job)
    assert captured["default_headers"]=={"X-DragonZpyder-Parent-Job-Id":job}
    runtime.model_client()
    assert captured["default_headers"] is None
