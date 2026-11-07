"""No-cost integration contracts for the opt-in Deep Agents harness."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_harness_uses_real_deepagents_and_is_agentic():
    from langchain_openrouter import ChatOpenRouter
    from langgraph.checkpoint.memory import MemorySaver
    from agent_platform.harness import build_frontier_agent
    model = ChatOpenRouter(model="openai/gpt-oss-120b", api_key="test")
    agent = build_frontier_agent(model, MemorySaver())
    assert hasattr(agent, "ainvoke")
    assert hasattr(agent, "astream")
    assert hasattr(agent, "aget_state")


def test_specialists_cannot_inherit_external_tools():
    from agent_platform.harness import specialist_specs, VIRTUAL_TOOLS
    specs = specialist_specs()
    assert {p["name"] for p in specs} == {"analyst", "verifier"}
    assert all(p["tools"] == [] for p in specs)
    assert "write_file" in VIRTUAL_TOOLS
    assert "edit_file" in VIRTUAL_TOOLS
    assert "execute" not in VIRTUAL_TOOLS
    assert "delete" not in VIRTUAL_TOOLS


def test_legacy_remains_default_and_feature_flag_selects_v2(monkeypatch):
    from langchain_openrouter import ChatOpenRouter
    from langgraph.checkpoint.memory import MemorySaver
    from agent_platform.runtime import build_agent
    model = ChatOpenRouter(model="openai/gpt-oss-120b", api_key="test")
    monkeypatch.delenv("DRAGONZPYDER_AGENT_HARNESS_V2", raising=False)
    legacy = build_agent(model, MemorySaver())
    assert hasattr(legacy, "ainvoke")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_HARNESS_V2", "1")
    frontier = build_agent(model, MemorySaver())
    assert hasattr(frontier, "ainvoke")
