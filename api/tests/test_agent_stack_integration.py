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
