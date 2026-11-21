"""Fail-closed Hatchet Personal wake setup; no credentials or model calls."""
from __future__ import annotations

import os
from pathlib import Path
import sys
from unittest.mock import patch

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_platform.personal_wake import PersonalWakeInput, require_wake_gate


def _base():
    return {
        "DRAGONZPYDER_PERSONAL_MCP_SCHEDULED_ENABLED": "1",
        "DRAGONZPYDER_AGENT_USE_GATEWAY": "1",
        "DRAGONZPYDER_AGENT_PRODUCTION_MODE": "1",
        "DRAGONZPYDER_OPERLY_MCP_ENABLED": "1",
        "DRAGONZPYDER_OPERLY_TOOLS_ENABLED": "1",
        "DRAGONZPYDER_PERSONAL_MCP_MUTATIONS_ENABLED": "0",
        "DRAGONZPYDER_AGENT_DATABASE_URL": "postgresql://fixture.invalid/checkpoints",
        "DRAGONZPYDER_OPERLY_MCP_SERVICE_SECRET": "a" * 48,
        "DRAGONZPYDER_OPERLY_PERSONAL_AGENT_TOKEN": "b" * 48,
        "DRAGONZPYDER_OPERLY_PERSONAL_RENEW_URL":
            "https://operly.dragonzpyder.xyz/api/internal/dragonzpyder/personal-mcp-delegation",
        "DRAGONZPYDER_OPERLY_PERSONAL_RUN_URL":
            "https://api.dragonzpyder.xyz/internal/agents/operly/personal/run",
    }


def test_wake_requires_explicit_gate_and_backend_authority():
    with patch.dict(os.environ, _base(), clear=False):
        dsn, proof, token, source, target = require_wake_gate()
        assert dsn.startswith("postgresql:")
        assert len(proof) >= 40 and len(token) >= 40
        assert source.startswith("https://operly.dragonzpyder.xyz/")
        assert target.startswith("https://api.dragonzpyder.xyz/")
        os.environ["DRAGONZPYDER_PERSONAL_MCP_SCHEDULED_ENABLED"] = "0"
        with pytest.raises(RuntimeError, match="disabled"):
            require_wake_gate()


def test_wake_rejects_unapproved_host_and_writes():
    with patch.dict(os.environ, _base(), clear=False):
        os.environ["DRAGONZPYDER_OPERLY_PERSONAL_RENEW_URL"] = (
            "https://untrusted.example/api/internal/dragonzpyder/personal-mcp-delegation"
        )
        with pytest.raises(RuntimeError, match="Unapproved"):
            require_wake_gate()
    with patch.dict(os.environ, _base(), clear=False):
        os.environ["DRAGONZPYDER_PERSONAL_MCP_MUTATIONS_ENABLED"] = "1"
        with pytest.raises(RuntimeError, match="read-only"):
            require_wake_gate()


def test_personal_wake_input_bounds_and_no_extra_authority():
    known = dict(goal_id="01234567-89ab-4cde-8123-000000000001",
                 user_id="01234567-89ab-4cde-8123-000000000002",
                 session_id="01234567-89ab-4cde-8123-000000000003",
                 conversation_id="01234567-89ab-4cde-8123-000000000004",
                 sequence=0, total_wakes=3, prompt="Inspect my Personal tasks")
    assert PersonalWakeInput(**known).total_wakes == 3
    with pytest.raises(ValidationError):
        PersonalWakeInput(**{**known, "total_wakes": 1})
    with pytest.raises(ValidationError):
        PersonalWakeInput(**{**known, "service_token": "forbidden"})
