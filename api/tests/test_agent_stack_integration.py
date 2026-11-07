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
