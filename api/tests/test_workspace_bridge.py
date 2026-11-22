"""Workspace bridge always requires first-party service authentication."""
import os
import sys
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_platform.workspace_bridge import router, workspace_thread


def test_checkpoint_key_scopes_user_and_workspace():
    value = workspace_thread("user-123", "tenant-123", "conversation-123")
    assert len(value) == 64
    assert value != workspace_thread("user-123", "tenant-456", "conversation-123")
    assert value != workspace_thread("user-456", "tenant-123", "conversation-123")


def test_reject_unauthenticated_browser_and_personal_scope():
    app = FastAPI()
    app.include_router(router)
    payload = dict(
        scope_kind="workspace", user_id="user-1234",
        workspace_id="space-1234", session_id="session-1234",
        conversation_id="conversation-1234", prompt="List my tasks",
        mcp_access_token="synthetic-token-" + "x" * 40,
        approved_tool_names=["tasks.list"],
    )
    with patch.dict(os.environ, {}, clear=True):
        with TestClient(app) as client:
            assert client.post("/internal/agents/operly/workspace/run", json=payload).status_code == 401
    with patch.dict(os.environ, {"DRAGONZPYDER_OPERLY_WORKSPACE_HARNESS_ENABLED": "1"}, clear=True):
        with TestClient(app) as client:
            assert client.post("/internal/agents/operly/workspace/run", json=payload).status_code == 401
            assert client.post("/internal/agents/operly/workspace/run",
                               json={**payload, "scope_kind": "personal"}).status_code == 422
