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


def test_scheduled_read_selects_exact_authorized_capability():
    from agent_platform.personal_wake import select_readonly_wake_tool
    capabilities = ["workflow.list", "tasks.list", "system.runtime.status"]
    assert select_readonly_wake_tool(
        "Check my Operly workflows every two minutes", capabilities
    ) == "workflow.list"
    assert select_readonly_wake_tool(
        "List my personal tasks", capabilities
    ) == "tasks.list"
    assert select_readonly_wake_tool(
        "Monitor system status", capabilities
    ) == "system.runtime.status"
    assert select_readonly_wake_tool(
        "Delete the invoices", capabilities
    ) is None
    assert select_readonly_wake_tool(
        "Check my workflows", ["tasks.list"]
    ) is None


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


def test_wake_database_can_be_bound_to_personal_api_without_overwriting_worker_checkpoints():
    with patch.dict(os.environ, _base(), clear=False):
        # A worker may have a different checkpoint database for unrelated
        # jobs, but Personal wake receipts MUST share the API goal database.
        os.environ["DRAGONZPYDER_PERSONAL_MCP_DATABASE_URL"] = (
            "postgresql://fixture.invalid/personal_goal_store"
        )
        assert require_wake_gate()[0] == (
            "postgresql://fixture.invalid/personal_goal_store"
        )
        assert os.environ["DRAGONZPYDER_AGENT_DATABASE_URL"] == (
            "postgresql://fixture.invalid/checkpoints"
        )


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


def test_only_authored_inference_quota_responses_pause_a_wake():
    from types import SimpleNamespace
    from agent_platform.personal_wake import pause_reason_from_reply

    rate_limited = SimpleNamespace(status_code=503, json=lambda: {
        "detail": {"code": "INFERENCE_LIMIT_REACHED", "message": "retry later"}
    })
    checkpointed = SimpleNamespace(status_code=200, json=lambda: {
        "status": "incomplete",
        "termination_reason": "inference_limit_reached",
        "successful_tools": [],
    })
    assert pause_reason_from_reply(rate_limited) == "inference_limit_reached"
    assert pause_reason_from_reply(checkpointed) == "inference_limit_reached"
    unknown_error = SimpleNamespace(status_code=503, json=lambda: {
        "detail": {"code": "INFERENCE_PROVIDER_UNAVAILABLE"}
    })
    assert pause_reason_from_reply(unknown_error) is None
    arbitrary_error = SimpleNamespace(status_code=503, json=lambda: {
        "detail": "Inference limit reached"
    })
    assert pause_reason_from_reply(arbitrary_error) is None
    malformed_error = SimpleNamespace(status_code=503, json=lambda: (_ for _ in ()).throw(ValueError()))
    assert pause_reason_from_reply(malformed_error) is None
    assert pause_reason_from_reply(SimpleNamespace(status_code=429, json=lambda: {})) is None


def test_goal_controller_plan_is_bounded_and_requires_opt_in():
    import asyncio
    from unittest.mock import AsyncMock
    from agent_platform.personal_wake import (
        PersonalGoalPlanInput, execute_personal_goal_plan,
        make_personal_goal_controller_task,
    )
    base = dict(
        goal_id="01234567-89ab-4cde-8123-000000000001",
        user_id="01234567-89ab-4cde-8123-000000000002",
        session_id="01234567-89ab-4cde-8123-000000000003",
        conversation_id="01234567-89ab-4cde-8123-000000000004",
        total_wakes=2,
        prompt="Check my personal tasks",
    )
    plan = PersonalGoalPlanInput(**base)
    with pytest.raises(ValidationError):
        PersonalGoalPlanInput(**{**base, "total_wakes": 4})
    with pytest.raises(ValidationError):
        PersonalGoalPlanInput(**{**base, "access_token": "unsafe"})
    with patch.dict(os.environ, _base(), clear=False):
        os.environ["DRAGONZPYDER_PERSONAL_GOAL_CONTROLLER_ENABLED"] = "0"
        with pytest.raises(RuntimeError, match="not enabled"):
            make_personal_goal_controller_task(object())
        with patch("agent_platform.personal_wake.perform_personal_wake",
                   new_callable=AsyncMock) as wake:
            wake.side_effect = [
                {"state": "active", "next_sequence": 1},
                {"state": "completed", "next_sequence": 2},
            ]
            result = asyncio.run(execute_personal_goal_plan(plan))
            assert result["state"] == "completed"
            assert result["verification"] == "postgres_receipts_only"
            assert [call.args[0].sequence for call in wake.await_args_list] == [0, 1]


def test_goal_controller_never_proceeds_after_pause_or_fails_stale_state():
    import asyncio
    from unittest.mock import AsyncMock
    from agent_platform.personal_wake import PersonalGoalPlanInput, execute_personal_goal_plan
    plan = PersonalGoalPlanInput(
        goal_id="01234567-89ab-4cde-8123-000000000001",
        user_id="01234567-89ab-4cde-8123-000000000002",
        session_id="01234567-89ab-4cde-8123-000000000003",
        conversation_id="01234567-89ab-4cde-8123-000000000004",
        total_wakes=2,
        prompt="Check tasks",
    )
    with patch.dict(os.environ, _base(), clear=False):
        with patch("agent_platform.personal_wake.perform_personal_wake",
                   new_callable=AsyncMock) as wake:
            wake.return_value = {"state": "paused_budget", "next_sequence": 0}
            paused = asyncio.run(execute_personal_goal_plan(plan))
            assert paused["requires_authorized_resume"] is True
            wake.assert_awaited_once()
        with patch("agent_platform.personal_wake.perform_personal_wake",
                   new_callable=AsyncMock) as wake:
            wake.return_value = {"state": "active", "next_sequence": 0}
            with pytest.raises(RuntimeError, match="refusing replay"):
                asyncio.run(execute_personal_goal_plan(plan))
            wake.assert_awaited_once()
