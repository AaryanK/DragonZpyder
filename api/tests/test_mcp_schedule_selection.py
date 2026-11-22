"""Synthetic scheduling test: account aliases are trusted inputs, not model arguments.

This test proves Hatchet receives immutable non-secret account selections and
the Personal goal DB gets the selection fence before dispatch. It does not
replace an actual Hatchet + OAuth provider end-to-end run.
"""
import asyncio
import hashlib
import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_platform import personal_goal_tools as scheduling


class GoalDatabase:
    def __init__(self):
        self.executed = []

    @asynccontextmanager
    async def transaction(self):
        yield self

    async def execute(self, sql, *params):
        self.executed.append((sql, params))
        return "INSERT 0 1"

    async def fetchval(self, *_):
        return 0

    async def fetchrow(self, *_):
        return None


class GoalPool:
    def __init__(self, connection):
        self.connection = connection

    @asynccontextmanager
    async def acquire(self):
        yield self.connection

    async def close(self):
        pass


def test_hatchet_wake_inherits_signed_account_selection(monkeypatch):
    user, session, conversation = (str(uuid4()) for _ in range(3))
    alice = "c" + "a" * 30
    bob = "c" + "b" * 30
    selections = [bob, alice]
    db = GoalDatabase()
    scheduled = []

    async def make_pool(*args, **kwargs):
        return GoalPool(db)

    class ScheduledTask:
        async def aio_schedule(self, *, run_at, input):
            scheduled.append((run_at, input.model_dump()))

    monkeypatch.setattr("asyncpg.create_pool", make_pool)
    monkeypatch.setattr(scheduling, "make_personal_mcp_wake_task",
                        lambda hatchet: ScheduledTask())
    monkeypatch.setitem(sys.modules, "hatchet_sdk",
                        SimpleNamespace(Hatchet=lambda: object()))
    monkeypatch.setenv("DRAGONZPYDER_PERSONAL_GOAL_TOOLS_ENABLED", "1")
    monkeypatch.setenv("DRAGONZPYDER_PERSONAL_MCP_SCHEDULED_ENABLED", "1")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_DATABASE_URL",
                       "postgresql://unreachable.local/synthetic")
    monkeypatch.setenv("HATCHET_CLIENT_TOKEN", "synthetic-test-only")
    monkeypatch.setenv("DRAGONZPYDER_MCP_USER_CONNECTIONS_ENABLED", "1")
    monkeypatch.setenv("DRAGONZPYDER_MCP_EGRESS_FIREWALL_ENFORCED", "1")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "staging")
    tool = scheduling.personal_goal_tools(
        user_id=user, session_id=session, conversation_id=conversation,
        mcp_connection_ids=selections,
    )[0]
    # The agent can specify a goal, never change an already trusted account.
    assert "mcp_connection_ids" not in tool.args
    result = asyncio.run(tool.ainvoke({
        "objective": "Check status", "interval_minutes":2, "occurrences":3,
    }))
    assert result["status"] == "scheduled"
    assert len(scheduled) == 3
    assert all(item["mcp_connection_ids"] == selections for _, item in scheduled)
    goal_id = result["goal_id"]
    rows = [
        values for sql, values in db.executed
        if "INSERT INTO dz_mcp_goal_selections" in sql
    ]
    assert len(rows) == 1
    assert rows[0] == (
        goal_id, user, hashlib.sha256(json.dumps(sorted(selections)).encode()).hexdigest()
    )


def test_signed_account_selection_rejects_duplicates_and_untrusted_aliases():
    args = {"user_id": str(uuid4()), "session_id": str(uuid4()),
            "conversation_id": str(uuid4())}
    for selected in (["c" + "a" * 30] * 2, ["not-an-account-id"]):
        with pytest.raises(RuntimeError, match="Invalid signed"):
            scheduling.personal_goal_tools(**args, mcp_connection_ids=selected)
