"""Signed Operly Workspace uses DragonZpyder's shared tool-enabled harness.

No provider calls or paid model calls. Workspace authority and Personal
authority have independent gates and differently scoped checkpoint IDs.
"""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_platform import workspace_bridge as bridge
from agent_platform.personal_bridge import _authorized
from main import app


def valid_payload(*, user="user-00000001", workspace="ws-00000001", conversation="conv-00000001"):
    return bridge.WorkspaceRun(
        scope_kind="workspace", user_id=user, workspace_id=workspace,
        session_id="session-0000001", conversation_id=conversation,
        prompt="Summarize the workspace.", mcp_access_token="x" * 48,
        approved_tool_names=["tasks.list"],
    )


def test_workspace_checkpoint_isolated_across_users_and_tenants():
    one = bridge.workspace_thread("user-00000001", "ws-00000001", "conv-00000001")
    assert one != bridge.workspace_thread("user-00000002", "ws-00000001", "conv-00000001")
    assert one != bridge.workspace_thread("user-00000001", "ws-00000002", "conv-00000001")
    assert one != bridge.workspace_thread("user-00000001", "ws-00000001", "conv-00000002")
    with pytest.raises(ValidationError):
        bridge.WorkspaceRun(**{**valid_payload().model_dump(), "scope_kind": "personal"})
    with pytest.raises(ValidationError):
        bridge.WorkspaceRun(**{**valid_payload().model_dump(), "product_surface": "dragonzpyder"})


def test_workspace_and_personal_authorization_separately_gated(monkeypatch):
    for k in [
        "DRAGONZPYDER_AGENTS_ENABLED", "DRAGONZPYDER_AGENT_HARNESS_V2",
        "DRAGONZPYDER_OPERLY_TOOLS_ENABLED", "DRAGONZPYDER_OPERLY_MCP_ENABLED",
        "DRAGONZPYDER_AGENT_USE_GATEWAY", "DRAGONZPYDER_AGENT_PRODUCTION_MODE",
    ]:
        monkeypatch.setenv(k, "1")
    monkeypatch.setenv("DRAGONZPYDER_OPERLY_PERSONAL_AGENT_TOKEN", "a" * 48)
    monkeypatch.setenv("DRAGONZPYDER_OPERLY_MCP_SERVICE_SECRET", "b" * 48)
    monkeypatch.delenv("DRAGONZPYDER_PERSONAL_MCP_HARNESS_ENABLED", raising=False)
    monkeypatch.setenv("DRAGONZPYDER_OPERLY_WORKSPACE_HARNESS_ENABLED", "1")
    assert _authorized("Bearer " + "a" * 48, "b" * 48, scope="workspace")
    assert not _authorized("Bearer " + "a" * 48, "b" * 48, scope="personal")
    assert not _authorized("Bearer " + "a" * 48, "wrong", scope="workspace")
    monkeypatch.setenv("DRAGONZPYDER_OPERLY_WORKSPACE_HARNESS_ENABLED", "0")
    assert not _authorized("Bearer " + "a" * 48, "b" * 48, scope="workspace")


def test_workspace_bridge_disallows_browser_or_unsupported_credentials(monkeypatch):
    monkeypatch.delenv("DRAGONZPYDER_OPERLY_WORKSPACE_HARNESS_ENABLED", raising=False)
    with TestClient(app) as client:
        response = client.post("/internal/agents/operly/workspace/run",
                               json=valid_payload().model_dump())
        assert response.status_code == 401
        assert "Signed Workspace" in response.json()["detail"]
