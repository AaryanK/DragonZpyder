"""Contract-level tests for signed Personal scheduled-goal tools.

Run from api/: python -m pytest -q tests/test_personal_goal_tools.py
These tests deliberately do not contact Hatchet, Operly or PostgreSQL.
"""
import asyncio
import sys
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_platform.personal_goal_tools import personal_goal_tools


def _ids():
    return dict(user_id=str(uuid4()), session_id=str(uuid4()),
                conversation_id=str(uuid4()))


def test_model_cannot_select_user_identity():
    tools = personal_goal_tools(**_ids())
    assert {tool.name for tool in tools} == {
        "goal_schedule", "goal_status", "goal_cancel",
    }
    schema = tools[0].args_schema.model_json_schema()
    assert "user_id" not in schema["properties"]
    assert "session_id" not in schema["properties"]
    assert "conversation_id" not in schema["properties"]


def test_noncanonical_scope_fails_closed():
    with pytest.raises(RuntimeError, match="Canonical"):
        personal_goal_tools(user_id="another-user", session_id=str(uuid4()),
                            conversation_id=str(uuid4()))


def test_rejects_unbounded_wakes_before_database_access():
    schedule = personal_goal_tools(**_ids())[0]
    with patch("agent_platform.personal_goal_tools._schedule_gate",
               return_value="postgresql://fake"):
        reply = asyncio.run(schedule.ainvoke({
            "objective": "Read workflow status",
            "interval_minutes": 2, "occurrences": 30,
        }))
    assert reply["status"] == "rejected"
    assert reply["reason"] == "occurrences_out_of_bounds"


def test_rejects_too_frequent_scheduling():
    schedule = personal_goal_tools(**_ids())[0]
    with patch("agent_platform.personal_goal_tools._schedule_gate",
               return_value="postgresql://fake"):
        reply = asyncio.run(schedule.ainvoke({
            "objective": "Read workflow status",
            "interval_minutes": 1, "occurrences": 5,
        }))
    assert reply["status"] == "rejected"
    assert reply["reason"] == "interval_out_of_bounds"
