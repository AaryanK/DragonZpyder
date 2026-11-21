"""First-party Operly session boundary and durable thread isolation."""
from __future__ import annotations

import os
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_platform.personal_bridge import _authorized, personal_thread


def _env():
    return {
        "DRAGONZPYDER_PERSONAL_MCP_HARNESS_ENABLED": "1",
        "DRAGONZPYDER_AGENTS_ENABLED": "1",
        "DRAGONZPYDER_AGENT_HARNESS_V2": "1",
        "DRAGONZPYDER_OPERLY_TOOLS_ENABLED": "1",
        "DRAGONZPYDER_OPERLY_MCP_ENABLED": "1",
        "DRAGONZPYDER_AGENT_USE_GATEWAY": "1",
        "DRAGONZPYDER_AGENT_PRODUCTION_MODE": "1",
        "DRAGONZPYDER_OPERLY_PERSONAL_AGENT_TOKEN": "a" * 48,
        "DRAGONZPYDER_OPERLY_MCP_SERVICE_SECRET": "b" * 48,
    }


def test_personal_route_requires_both_independent_secrets_and_feature_flags():
    with patch.dict(os.environ, _env(), clear=False):
        assert _authorized("Bearer " + "a" * 48, "b" * 48)
        assert not _authorized("Bearer " + "a" * 48, "")
        assert not _authorized("Bearer " + "z" * 48, "b" * 48)
        os.environ["DRAGONZPYDER_PERSONAL_MCP_HARNESS_ENABLED"] = "0"
        assert not _authorized("Bearer " + "a" * 48, "b" * 48)


def test_personal_checkpoints_derive_from_owner_and_conversation():
    a = personal_thread("user-A", "conversation-x")
    b = personal_thread("user-B", "conversation-x")
    c = personal_thread("user-A", "conversation-y")
    assert len(a) == 64
    assert len({a, b, c}) == 3
    assert a == personal_thread("user-A", "conversation-x")
    assert "user-A" not in a and "conversation-x" not in a


def test_personal_route_disabled_by_default(monkeypatch):
    for k in ("DRAGONZPYDER_PERSONAL_MCP_HARNESS_ENABLED",
              "DRAGONZPYDER_OPERLY_MCP_ENABLED"):
        monkeypatch.delenv(k, raising=False)
    assert not _authorized("Bearer " + "a" * 48, "b" * 48)
