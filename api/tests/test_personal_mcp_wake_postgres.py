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
        shifted = first.model_copy(update={
            "sequence": 1, "prompt": "Do an unrelated task instead",
        })
        with pytest.raises(RuntimeError, match="authority changed"):
            await perform_personal_wake(shifted, http=SimulatedRemote())

    with patch.dict(os.environ, _vars(dsn), clear=False):
        asyncio.run(run())


class QuotaRemote(SimulatedRemote):
    async def post(self, url, **kwargs):
        self.calls.append((url, kwargs.get("json", {})))
        if "/personal-mcp-delegation" in url:
            return SimpleNamespace(
                status_code=200,
                json=lambda: {
                    "access_token": "temporary-fixture-" + "t" * 64,
                    "approved_tool_names": ["tasks.list"],
                },
            )
        assert url.endswith("/internal/agents/operly/personal/run")
        return SimpleNamespace(
            status_code=503,
            json=lambda: {"detail": {"code": "INFERENCE_LIMIT_REACHED"}},
        )


def test_quota_pauses_goal_without_advancing_or_replaying_next_wake():
    dsn = os.environ["DRAGONZPYDER_BUDGET_TEST_DSN"]
    goal_id, user_id, session_id, conversation_id = (str(uuid4()) for _ in range(4))

    async def run():
        wake = _input(goal_id=goal_id, user_id=user_id,
                      session_id=session_id, conversation_id=conversation_id,
                      sequence=0)
        quota = QuotaRemote()
        outcome = await perform_personal_wake(wake, http=quota)
        assert outcome["state"] == "paused_budget"
        assert outcome["reason"] == "inference_limit_reached"
        assert outcome["requires_authorized_resume"] is True
        assert outcome["next_sequence"] == 0
        assert len(quota.calls) == 2
        second_attempt = SimulatedRemote()
        duplicate = await perform_personal_wake(wake, http=second_attempt)
        assert duplicate["state"] == "paused_budget"
        assert duplicate["reason"] == "already_processed"
        assert duplicate["model_calls"] == 0
        assert second_attempt.calls == []
        con = await asyncpg.connect(dsn)
        try:
            result = await con.fetchrow(
                "SELECT state,next_sequence FROM dz_personal_mcp_goals WHERE goal_id=$1",
                goal_id,
            )
            assert result["state"] == "paused_budget"
            assert result["next_sequence"] == 0
            assert await con.fetchval(
                "SELECT count(*) FROM dz_personal_mcp_receipts WHERE goal_id=$1",
                goal_id,
            ) == 0
        finally:
            await con.close()

    with patch.dict(os.environ, _vars(dsn), clear=False):
        asyncio.run(run())


def test_quota_pause_never_allows_later_sequence_to_run():
    dsn = os.environ["DRAGONZPYDER_BUDGET_TEST_DSN"]
    goal_id, user_id, session_id, conversation_id = (str(uuid4()) for _ in range(4))

    async def run():
        first = _input(goal_id=goal_id, user_id=user_id,
                       session_id=session_id, conversation_id=conversation_id,
                       sequence=0)
        await perform_personal_wake(first, http=QuotaRemote())
        later = SimulatedRemote()
        result = await perform_personal_wake(
            first.model_copy(update={"sequence": 1}), http=later
        )
        assert result["state"] == "paused_budget"
        assert result["model_calls"] == 0
        assert later.calls == []

    with patch.dict(os.environ, _vars(dsn), clear=False):
        asyncio.run(run())


def test_operator_resume_revalidates_session_and_never_dispatches_automatically():
    from agent_platform.personal_wake import operator_resume_paused_personal_goal
    dsn = os.environ["DRAGONZPYDER_BUDGET_TEST_DSN"]
    goal_id, user_id, session_id, conversation_id = (str(uuid4()) for _ in range(4))

    async def run():
        wake = _input(goal_id=goal_id, user_id=user_id,
                      session_id=session_id, conversation_id=conversation_id,
                      sequence=0)
        await perform_personal_wake(wake, http=QuotaRemote())
        with pytest.raises(RuntimeError, match="disabled"):
            await operator_resume_paused_personal_goal(wake, http=SimulatedRemote())
        os.environ["DRAGONZPYDER_PERSONAL_MCP_RESUME_OPERATOR_ALLOWED"] = "1"
        with pytest.raises(RuntimeError, match="cannot authorize resume"):
            await operator_resume_paused_personal_goal(
                wake, http=SimulatedRemote(revoke=True)
            )
        with pytest.raises(RuntimeError, match="mismatch"):
            await operator_resume_paused_personal_goal(
                wake.model_copy(update={"prompt": "Different objective"}),
                http=SimulatedRemote(),
            )
        renewed = SimulatedRemote()
        resumed = await operator_resume_paused_personal_goal(wake, http=renewed)
        assert resumed == {"state": "active", "next_sequence": 0,
                           "scheduled": False, "requires_hatchet_dispatch": True}
        assert len(renewed.calls) == 1  # Only authority revalidation, no agent run.
        with pytest.raises(RuntimeError, match="not paused"):
            await operator_resume_paused_personal_goal(wake, http=SimulatedRemote())
        complete = await perform_personal_wake(wake, http=SimulatedRemote())
        assert complete["state"] == "active"
        assert complete["next_sequence"] == 1

    with patch.dict(os.environ, {
        **_vars(dsn),
        "DRAGONZPYDER_PERSONAL_MCP_RESUME_OPERATOR_ALLOWED": "0",
    }, clear=False):
        asyncio.run(run())


class AmbiguousAgentRemote(SimulatedRemote):
    async def post(self, url, **kwargs):
        self.calls.append((url, kwargs.get("json", {})))
        if "/personal-mcp-delegation" in url:
            return SimpleNamespace(
                status_code=200,
                json=lambda: {"access_token": "temporary-fixture-" + "t" * 64,
                              "approved_tool_names": ["tasks.list"]},
            )
        # A remote agent may have performed a tool effect before its connection
        # dropped or returned 502; neither outcome proves it is safe to retry.
        assert url.endswith("/internal/agents/operly/personal/run")
        return SimpleNamespace(status_code=502, json=lambda: {})


def test_ambiguous_remote_failure_persists_inflight_fence_and_never_replays():
    dsn = os.environ["DRAGONZPYDER_BUDGET_TEST_DSN"]
    ids = [str(uuid4()) for _ in range(4)]
    async def run():
        first = _input(goal_id=ids[0], user_id=ids[1],
                       session_id=ids[2], conversation_id=ids[3], sequence=0)
        remote = AmbiguousAgentRemote()
        with pytest.raises(RuntimeError, match="execution rejected"):
            await perform_personal_wake(first, http=remote)
        assert len(remote.calls) == 2
        # Simulate another worker/connection after a restart: no HTTP is sent.
        next_worker = SimulatedRemote()
        outcome = await perform_personal_wake(first, http=next_worker)
        assert outcome == {
            "state": "inflight", "next_sequence": 0,
            "model_calls": 0, "reason": "inflight_outcome_uncertain",
        }
        assert next_worker.calls == []
        con = await asyncpg.connect(dsn)
        try:
            row = await con.fetchrow(
                "SELECT state, next_sequence FROM dz_personal_mcp_goals WHERE goal_id=$1",
                ids[0],
            )
            assert row["state"] == "inflight"
            assert row["next_sequence"] == 0
            assert await con.fetchval(
                "SELECT count(*) FROM dz_personal_mcp_receipts WHERE goal_id=$1",
                ids[0],
            ) == 0
        finally:
            await con.close()
    with patch.dict(os.environ, _vars(dsn), clear=False):
        asyncio.run(run())
