"""Security contract for independently signed Operly Workspace delegation.

No model inference or provider call is executed by these tests.
"""
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_platform import workspace_bridge as bridge
from main import app


def payload(*, workspace=None, user=None, conversation=None):
    uid = user or uuid4()
    return bridge.WorkspaceRun(
        scope_kind="workspace",
        workspace_id=workspace or uuid4(),
        user_id=uid,
        principal_id=f"user:{uid}",
        conversation_id=conversation or uuid4(),
        prompt="Summarize work.",
    )


def test_workspace_delegation_requires_two_separate_server_proofs(monkeypatch):
    t = "a" * 48
    s = "b" * 48
    monkeypatch.setenv("DRAGONZPYDER_WORKSPACE_DELEGATION_ENABLED", "1")
    monkeypatch.setenv("DRAGONZPYDER_AGENTS_ENABLED", "1")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_USE_GATEWAY", "1")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_PRODUCTION_MODE", "1")
    monkeypatch.setenv("DRAGONZPYDER_OPERLY_WORKSPACE_AGENT_TOKEN", t)
    monkeypatch.setenv("DRAGONZPYDER_OPERLY_WORKSPACE_SERVICE_SECRET", s)
    assert bridge._authorized("Bearer " + t, s)
    assert not bridge._authorized("Bearer " + t, "bad")
    assert not bridge._authorized("Bearer wrong", s)
    monkeypatch.setenv("DRAGONZPYDER_OPERLY_WORKSPACE_SERVICE_SECRET", t)
    assert not bridge._authorized("Bearer " + t, t)
    monkeypatch.setenv("DRAGONZPYDER_WORKSPACE_DELEGATION_ENABLED", "0")
    assert not bridge._authorized("Bearer " + t, t)


def test_workspace_owner_and_thread_isolation():
    one = payload()
    a = bridge.workspace_thread(one)
    assert a == bridge.workspace_thread(one)
    assert a != bridge.workspace_thread(payload(user=one.user_id,
                                               conversation=one.conversation_id))
    assert a != bridge.workspace_thread(payload(workspace=one.workspace_id,
                                               conversation=one.conversation_id))
    with pytest.raises(ValidationError):
        bridge.WorkspaceRun(**{**one.model_dump(), "scope_kind": "personal"})
    with pytest.raises(ValidationError):
        bridge.WorkspaceRun(**{**one.model_dump(), "mcp_access_token": "unsafe"})


def test_workspace_endpoint_disabled_for_browsers(monkeypatch):
    monkeypatch.delenv("DRAGONZPYDER_WORKSPACE_DELEGATION_ENABLED", raising=False)
    with TestClient(app) as client:
        assert client.post(
            "/internal/agents/operly/workspace/run", json=payload().model_dump(mode="json")
        ).status_code == 401
