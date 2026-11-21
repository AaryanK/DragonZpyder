"""Actual PostgreSQL two-wake ledger + revocation acceptance (no paid models).

Transport is intentionally simulated: this proves durable state, exactly-once
receipt semantics for these read-only wake steps, and zero-run revocation, NOT
that the new MCP network route or a live LLM has been tested.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import asyncpg
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_platform.personal_wake import PersonalWakeInput, perform_personal_wake


def _vars(dsn):
    return {
        "DRAGONZPYDER_STAGE": "staging",
        "DRAGONZPYDER_PERSONAL_MCP_SCHEDULED_ENABLED": "1",
        "DRAGONZPYDER_AGENT_USE_GATEWAY": "1",
        "DRAGONZPYDER_AGENT_PRODUCTION_MODE": "1",
        "DRAGONZPYDER_OPERLY_MCP_ENABLED": "1",
        "DRAGONZPYDER_OPERLY_TOOLS_ENABLED": "1",
        "DRAGONZPYDER_PERSONAL_MCP_MUTATIONS_ENABLED": "0",
        "DRAGONZPYDER_PERSONAL_MCP_SCHEMA_INSTALL_ALLOWED": "1",
        "DRAGONZPYDER_AGENT_DATABASE_URL": dsn,
        "DRAGONZPYDER_OPERLY_MCP_SERVICE_SECRET": "q" * 48,
        "DRAGONZPYDER_OPERLY_PERSONAL_AGENT_TOKEN": "r" * 48,
        "DRAGONZPYDER_OPERLY_PERSONAL_RENEW_URL":
            "https://operly.dragonzpyder.xyz/api/internal/dragonzpyder/personal-mcp-delegation",
        "DRAGONZPYDER_OPERLY_PERSONAL_RUN_URL":
            "https://api.dragonzpyder.xyz/internal/agents/operly/personal/run",
    }


class SimulatedRemote:
    def __init__(self, *, revoke=False):
        self.revoke = revoke
        self.calls = []

    async def post(self, url, **kwargs):
        self.calls.append((url, kwargs.get("json", {})))
        if "/personal-mcp-delegation" in url:
            if self.revoke:
                return SimpleNamespace(status_code=403)
            return SimpleNamespace(
                status_code=200,
                json=lambda: {"access_token": "temporary-fixture-" + "t" * 64,
                              "approved_tool_names": ["tasks.list"]},
            )
        if url.endswith("/internal/agents/operly/personal/run"):
            assert kwargs["json"]["scope_kind"] == "personal"
            assert kwargs["json"]["approved_tool_names"] == ["tasks.list"]
            assert kwargs["headers"]["X-Operly-Agent-Service"] == "q" * 48
            return SimpleNamespace(
                status_code=200,
                json=lambda: {
                    "status": "completed",
                    "answer": "Fixture task listing completed.",
                    "successful_tools": ["operly_tasks_list"],
                },
            )
        raise AssertionError("unexpected endpoint")


def _input(*, goal_id, user_id, session_id, conversation_id, sequence):
    return PersonalWakeInput(
        goal_id=goal_id, user_id=user_id,
        session_id=session_id, conversation_id=conversation_id,
        sequence=sequence, total_wakes=2, prompt="List my personal tasks",
    )


def test_two_sequential_wakes_persist_receipts_and_skip_replays():
    dsn = os.environ["DRAGONZPYDER_BUDGET_TEST_DSN"]
    goal_id, user_id, session_id, conversation_id = (str(uuid4()) for _ in range(4))

    async def run():
        first = _input(goal_id=goal_id, user_id=user_id,
                       session_id=session_id, conversation_id=conversation_id,
                       sequence=0)
        second = first.model_copy(update={"sequence": 1})
        a = SimulatedRemote()
        outcome1 = await perform_personal_wake(first, http=a)
        assert outcome1["state"] == "active"
        assert outcome1["next_sequence"] == 1
        assert outcome1["tools"] == ["operly_tasks_list"]
        assert len(a.calls) == 2
        b = SimulatedRemote()
        repeated = await perform_personal_wake(first, http=b)
        assert repeated["reason"] == "already_processed"
        assert repeated["model_calls"] == 0
        assert b.calls == []
        c = SimulatedRemote()
        outcome2 = await perform_personal_wake(second, http=c)
        assert outcome2["state"] == "completed"
        assert outcome2["next_sequence"] == 2
        assert len(c.calls) == 2
        again = SimulatedRemote()
        terminal = await perform_personal_wake(second, http=again)
        assert terminal["model_calls"] == 0 and again.calls == []
        pool = await asyncpg.create_pool(dsn, min_size=1, max_size=1)
        try:
            async with pool.acquire() as con:
                goal = await con.fetchrow(
                    "SELECT state, next_sequence, user_id FROM dz_personal_mcp_goals WHERE goal_id=$1",
                    goal_id,
                )
                receipts = await con.fetch(
                    "SELECT sequence, status, tool_names FROM dz_personal_mcp_receipts "
                    "WHERE goal_id=$1 ORDER BY sequence", goal_id,
                )
                assert goal["state"] == "completed" and goal["next_sequence"] == 2
                assert goal["user_id"] == user_id
                assert [r["sequence"] for r in receipts] == [0, 1]
                assert all(r["status"] == "completed" for r in receipts)
        finally:
            await pool.close()

    with patch.dict(os.environ, _vars(dsn), clear=False):
        asyncio.run(run())


def test_revoked_session_blocks_future_wake_without_agent_call():
    dsn = os.environ["DRAGONZPYDER_BUDGET_TEST_DSN"]
    goal_id, user_id, session_id, conversation_id = (str(uuid4()) for _ in range(4))

    async def run():
        first = _input(goal_id=goal_id, user_id=user_id,
                       session_id=session_id, conversation_id=conversation_id,
                       sequence=0)
        assert (await perform_personal_wake(first, http=SimulatedRemote()))["state"] == "active"
        second = first.model_copy(update={"sequence": 1})
        remote = SimulatedRemote(revoke=True)
        blocked = await perform_personal_wake(second, http=remote)
        assert blocked["state"] == "blocked"
        assert blocked["model_calls"] == 0
        assert len(remote.calls) == 1  # Renewal denied; harness never called
        later = SimulatedRemote()
        assert (await perform_personal_wake(second, http=later))["state"] == "blocked"
        assert later.calls == []
        con = await asyncpg.connect(dsn)
        try:
            assert await con.fetchval(
                "SELECT count(*) FROM dz_personal_mcp_receipts WHERE goal_id=$1",
                goal_id,
            ) == 1
        finally:
            await con.close()

    with patch.dict(os.environ, _vars(dsn), clear=False):
        asyncio.run(run())


def test_existing_goal_cannot_be_retargeted_to_another_user():
    dsn = os.environ["DRAGONZPYDER_BUDGET_TEST_DSN"]
    goal_id, user_id, session_id, conversation_id = (str(uuid4()) for _ in range(4))

    async def run():
        first = _input(goal_id=goal_id, user_id=user_id, session_id=session_id,
                       conversation_id=conversation_id, sequence=0)
        await perform_personal_wake(first, http=SimulatedRemote())
        wrong = first.model_copy(update={"user_id": str(uuid4()), "sequence": 1})
        with pytest.raises(RuntimeError, match="authority changed"):
            await perform_personal_wake(wrong, http=SimulatedRemote())

    with patch.dict(os.environ, _vars(dsn), clear=False):
        asyncio.run(run())
