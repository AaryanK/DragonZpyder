"""SDK integration acceptance: no remote model requests, real graph construction."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

def test_real_agent_graph_construction_without_provider_call():
    from langchain_openrouter import ChatOpenRouter
    from langgraph.checkpoint.memory import MemorySaver
    from agent_platform.runtime import build_agent
    model = ChatOpenRouter(
        model="openai/gpt-oss-120b",
        api_key="test",
        max_tokens=768,
    )
    graph = build_agent(model, MemorySaver())
    assert hasattr(graph, "ainvoke")

def test_gateway_model_client_rejects_untrusted_or_missing_gateway(monkeypatch):
    import pytest
    from agent_platform.runtime import model_client
    monkeypatch.setenv("DRAGONZPYDER_AGENT_MODEL_ID", "openai/gpt-oss-120b")
    monkeypatch.setenv("DRAGONZPYDER_RUNTIME_ALLOWED_MODELS", "openai/gpt-oss-120b")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_USE_GATEWAY", "1")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_GATEWAY_TOKEN", "t" * 44)
    monkeypatch.setenv("DRAGONZPYDER_AGENT_GATEWAY_BASE_URL", "http://example.org/internal/agent/v1")
    with pytest.raises(RuntimeError):
        model_client()
    monkeypatch.setenv("DRAGONZPYDER_AGENT_GATEWAY_BASE_URL", "https://gateway.example.org/internal/agent/v1")
    model = model_client()
    assert model is not None
    monkeypatch.setenv("DRAGONZPYDER_AGENT_USE_GATEWAY", "0")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_PRODUCTION_MODE", "1")
    with pytest.raises(RuntimeError):
        model_client()


def test_metered_gateway_output_limit_is_bounded_and_opt_in(monkeypatch):
    import pytest
    from agent_platform.runtime import model_client
    monkeypatch.setenv("DRAGONZPYDER_AGENT_MODEL_ID", "openai/gpt-oss-120b")
    monkeypatch.setenv("DRAGONZPYDER_RUNTIME_ALLOWED_MODELS", "openai/gpt-oss-120b")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_USE_GATEWAY", "1")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_GATEWAY_TOKEN", "t" * 44)
    monkeypatch.setenv("DRAGONZPYDER_AGENT_GATEWAY_BASE_URL", "https://gateway.example.org/internal/agent/v1")
    monkeypatch.delenv("DRAGONZPYDER_AGENT_STRESS_EVAL_ENABLED", raising=False)
    monkeypatch.delenv("DRAGONZPYDER_AGENT_GATEWAY_OUTPUT_TOKENS", raising=False)
    assert model_client().max_tokens == 768
    for allowed in ("2048", "4096"):
        monkeypatch.setenv("DRAGONZPYDER_AGENT_GATEWAY_OUTPUT_TOKENS", allowed)
        client = model_client()
        assert client.max_tokens == int(allowed)
        assert client.max_retries == 0
    for rejected in ("0", "767", "4097", "-1", "abc", "", "02048"):
        monkeypatch.setenv("DRAGONZPYDER_AGENT_GATEWAY_OUTPUT_TOKENS", rejected)
        with pytest.raises(RuntimeError, match="output token ceiling"):
            model_client()


def test_graph_message_stream_uses_nonstreaming_metered_model_transport(monkeypatch):
    """Exercise actual SDK + LangGraph message stream against mocked HTTP gateway."""
    import asyncio, json, httpx
    from agent_platform.runtime import model_client
    from agent_platform.gateway_protocol import validate_agent_body
    from langgraph.graph import StateGraph, MessagesState, START, END
    monkeypatch.setenv("DRAGONZPYDER_AGENT_MODEL_ID", "openai/gpt-oss-120b")
    monkeypatch.setenv("DRAGONZPYDER_RUNTIME_ALLOWED_MODELS", "openai/gpt-oss-120b")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_USE_GATEWAY", "1")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_GATEWAY_TOKEN", "t" * 44)
    monkeypatch.setenv("DRAGONZPYDER_AGENT_GATEWAY_BASE_URL", "https://gateway.example.org/internal/agent/v1")
    model = model_client()
    assert model.disable_streaming is True
    calls = []
    async def gateway(request):
        body = json.loads(request.content)
        assert body.get("stream", False) is False
        validate_agent_body(body, ["openai/gpt-oss-120b"])
        calls.append(body)
        return httpx.Response(200, json={"id":"test-1","object":"chat.completion","created":1,
            "model":"openai/gpt-oss-120b","choices":[{"index":0,"message":{"role":"assistant","content":"42"},
            "finish_reason":"stop"}],"usage":{"prompt_tokens":10,"completion_tokens":1,"total_tokens":11}})
    async def scenario():
        from openai import AsyncOpenAI
        async with httpx.AsyncClient(transport=httpx.MockTransport(gateway)) as http:
            sdk = AsyncOpenAI(api_key="test", base_url="https://gateway.example.org/internal/agent/v1", http_client=http, max_retries=0)
            model.async_client = sdk.chat.completions
            model.root_async_client = sdk
            async def node(state):
                return {"messages":[await model.ainvoke(state["messages"])]}
            graph = StateGraph(MessagesState)
            graph.add_node("model",node)
            graph.add_edge(START,"model")
            graph.add_edge("model",END)
            values = []
            async for mode, event in graph.compile().astream({"messages":[{"role":"user","content":"Return 42"}]},stream_mode=["messages","values"]):
                if mode=="values": values.append(event)
            assert values[-1]["messages"][-1].content == "42"
            assert len(calls)==1
    asyncio.run(scenario())


def test_shared_builder_propagates_specialists_and_authorized_capabilities(monkeypatch):
    from agent_platform import runtime, harness
    for role in ("ANALYST","VERIFIER","RESEARCHER","BUILDER"):
        monkeypatch.setenv("DRAGONZPYDER_AGENT_"+role+"_MODEL_ID", "test/"+role.lower())
    calls=[]
    def model_client(**kwargs):
        calls.append(kwargs)
        return kwargs["model_override"]
    monkeypatch.setattr(runtime,"model_client",model_client)
    captured={}
    def factory(model,checkpointer,**kwargs):
        captured.update(kwargs)
        return "graph"
    monkeypatch.setattr(harness,"build_frontier_agent",factory)
    marker=object()
    assert runtime.build_agent("supervisor","checkpoint",parent_job_id="parent",delegated_tools=marker,routing_middleware=marker)=="graph"
    assert captured["delegated_tools"] is marker and captured["routing_middleware"] is marker
    assert captured["specialist_models"]=={x:"test/"+x for x in ("analyst","verifier","researcher","builder")}
    assert all(x["parent_job_id"]=="parent" for x in calls)
    calls.clear()
    runtime.build_agent("supervisor","checkpoint",artifact_tools=marker)
    assert captured["artifact_tools"] is marker and all("parent_job_id" not in x for x in calls)
