"""One agent implementation; product presentation is server-selected and
cannot expand tool authority or impersonate an unrelated user account.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_platform import harness


def test_one_shared_harness_but_distinct_product_presentation(monkeypatch):
    prompts = []
    def capture(**kwargs):
        prompts.append(kwargs["system_prompt"])
        return kwargs
    monkeypatch.setattr(harness, "create_deep_agent", capture)
    monkeypatch.delenv("DRAGONZPYDER_AGENT_WEB_SEARCH_ENABLED", raising=False)
    monkeypatch.delenv("DRAGONZPYDER_AGENT_QUICKJS_ENABLED", raising=False)

    default = harness.build_frontier_agent(
        object(), object(), product_surface="dragonzpyder")
    branded = harness.build_frontier_agent(
        object(), object(), product_surface="operly")
    assert default["backend"].__class__ is branded["backend"].__class__
    assert "DragonZpyder's general-purpose autonomous agent" in prompts[0]
    assert "Operly AI assistant inside the Operly" not in prompts[0]
    assert "Operly AI assistant inside the Operly" in prompts[1]
    assert "underlying agent execution platform" in prompts[1]
    assert "Only claim access to workspaces" in prompts[1]
    assert default["tools"] == branded["tools"]


def test_arbitrary_brand_or_client_selected_identity_rejected(monkeypatch):
    with pytest.raises(ValueError, match="Unknown agent product surface"):
        harness.build_frontier_agent(object(), object(), product_surface="custom-sso-spoof")
