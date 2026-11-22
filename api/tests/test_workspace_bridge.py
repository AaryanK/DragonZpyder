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


def test_harness_executes_only_signed_scoped_tools_and_persists_new_turn(monkeypatch):
    import types
    from unittest.mock import AsyncMock, patch
    from agent_platform.workspace_bridge import workspace_thread

    token = "opaque-backend-only-" + "k" * 40
    body = dict(
        scope_kind="workspace", user_id="user-1234", workspace_id="space-1234",
        session_id="session-1234", conversation_id="conversation-1234",
        prompt="Find pending invoices", mcp_access_token=token,
        approved_tool_names=["invoice.list"],
    )
    before = types.SimpleNamespace(values={"messages": []})
    after = types.SimpleNamespace(values={"messages": [
        types.SimpleNamespace(type="human", content=body["prompt"]),
    ]})
    class Agent:
        def __init__(self):
            self.read_count = 0
            self.calls = []
        async def aget_state(self, config):
            self.read_count += 1
            return before if self.read_count == 1 else after
        async def ainvoke(self, value, config):
            self.calls.append((value, config))
            return {"messages": []}
    agent = Agent()
    app = FastAPI()
    app.include_router(router)
    app.state.agent_runtime = types.SimpleNamespace(_checkpointer=object())
    with patch.dict(os.environ, {"DRAGONZPYDER_OPERLY_WORKSPACE_HARNESS_ENABLED": "1"}, clear=True), \
         patch("agent_platform.workspace_bridge._authorized", return_value=True), \
         patch("agent_platform.operly_mcp_client.load_authorized_operly_mcp_tools",
               new=AsyncMock(return_value=[types.SimpleNamespace(name="operly_invoice_list")])), \
         patch("agent_platform.harness.build_frontier_agent", return_value=agent), \
         patch("agent_platform.runtime.model_client", return_value=object()), \
         patch("agent_platform.runtime.summarize_agent_result",
               return_value={"status": "completed", "answer": "One pending invoice",
                             "successful_tools": ["operly_invoice_list"],
                             "failed_tool_count": 0}):
        with TestClient(app) as client:
            response = client.post("/internal/agents/operly/workspace/run", json=body)
    assert response.status_code == 200
    assert response.json()["answer"] == "One pending invoice"
    assert response.json()["thread_checkpointed"] is True
    assert len(agent.calls) == 1
    messages, config = agent.calls[0]
    assert messages == {"messages": [{"role": "user", "content": body["prompt"]}]}
    assert token not in str(messages)
    assert config["configurable"]["thread_id"] == workspace_thread(
        body["user_id"], body["workspace_id"], body["conversation_id"],
    )
