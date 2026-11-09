"""Real Postgres: web search baseline -> event -> one durable wake.

All web observations are injected deterministic fixtures; no external internet
or paid model. PostgreSQL transactions, row locks, uniqueness and cancellation
are real. The production path uses only the fixed-origin Wikipedia adapter.
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from agent_platform.goal_store import SCHEMA
from agent_platform.event_wait import EventWaitStore, EventWaitConflict
from agent_platform.web_event_watch import (
    register_operator_watch, check_web_watch, run_due_web_checks,
    require_web_event_gate,
)


def enable(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_WEB_EVENT_ENABLED", "1")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_WEB_SEARCH_ENABLED", "1")
    monkeypatch.setenv("DRAGONZPYDER_GOAL_SYNTHETIC_ONLY", "1")
    monkeypatch.setenv("DRAGONZPYDER_STAGE", "staging")


def source(title: str, url: str):
    return {"results": [{"title": title, "url": url, "snippet": "Public search result"}]}


def test_web_event_monitor_never_runs_without_operator_gates(monkeypatch):
    monkeypatch.delenv("DRAGONZPYDER_WEB_EVENT_ENABLED", raising=False)
    with pytest.raises(RuntimeError, match="staging"):
        require_web_event_gate()
    enable(monkeypatch)
    require_web_event_gate()
    monkeypatch.setenv("DRAGONZPYDER_STAGE", "production")
    with pytest.raises(RuntimeError, match="staging"):
        require_web_event_gate()


@pytest.mark.skipif(not os.getenv("DRAGONZPYDER_BUDGET_TEST_DSN"),
                    reason="Requires disposable PostgreSQL")
def test_event_wait_dedup_idempotent_search_restart_revocation_and_authorization(monkeypatch):
    import asyncpg
    enable(monkeypatch)

    async def scenario():
        dsn = os.environ["DRAGONZPYDER_BUDGET_TEST_DSN"]
        schema = "dz_events_" + uuid4().hex
        admin = await asyncpg.connect(dsn)
        pool = None
        clock = datetime.now(timezone.utc).replace(microsecond=0)
        try:
            await admin.execute('CREATE SCHEMA "' + schema + '"')
            pool = await asyncpg.create_pool(
                dsn=dsn, min_size=1, max_size=4,
                server_settings={"search_path": schema},
            )
            async with pool.acquire() as con:
                await con.execute(SCHEMA)

            await register_operator_watch(
                pool, monitor_id="wikipedia_ai_updates",
                query="artificial intelligence research", now=clock,
            )
            with pytest.raises(ValueError):
                await register_operator_watch(
                    pool, monitor_id="wikipedia_ai_updates",
                    query="different query", now=clock,
                )
            store = EventWaitStore(pool)
            internal = await store.subscribe(
                source_app="internal_canary", kind="personal",
                user_id="internal-staging-probe", workspace_id=None,
                request_id=str(uuid4()), monitor_id="wikipedia_ai_updates",
            )
            user_req = str(uuid4())
            personal = await store.subscribe(
                source_app="operly", kind="workspace",
                user_id="test-user", workspace_id="workspace-one",
                request_id=user_req, monitor_id="wikipedia_ai_updates",
            )
            again = await store.subscribe(
                source_app="operly", kind="workspace",
                user_id="test-user", workspace_id="workspace-one",
                request_id=user_req, monitor_id="wikipedia_ai_updates",
            )
            assert personal["wait_id"] == again["wait_id"]

            async def baseline_search(q, *, provider, limit):
                assert q == "artificial intelligence research"
                assert provider == "wikipedia" and limit == 3
                return source("Original", "https://en.wikipedia.org/wiki/Original")

            async def changed_search(q, *, provider, limit):
                return source("Changed", "https://en.wikipedia.org/wiki/Changed")

            first = await run_due_web_checks(
                pool, search=baseline_search, now=clock,
            )
            assert first["checks"][0]["status"] == "baseline_created"
            assert first["checks"][0]["event_published"] is False
            assert first["wakes"] == []
            assert await store.list_wakes(
                source_app="internal_canary", kind="personal",
                user_id="internal-staging-probe", workspace_id=None,
                wait_id=internal["wait_id"],
            ) == []

            quiet = await run_due_web_checks(
                pool, search=changed_search, now=clock + timedelta(seconds=1),
            )
            assert quiet["checks"] == []  # Not due before the approved interval.
            change_at = clock + timedelta(seconds=601)
            changed = await run_due_web_checks(
                pool, search=changed_search, now=change_at,
            )
            assert changed["checks"][0]["status"] == "changed"
            assert changed["checks"][0]["event_published"] is True
            assert changed["checks"][0]["wakes_created"] == 2
            assert len(changed["wakes"]) == 1
            assert changed["wakes"][0]["status"] == "completed"
            assert changed["wakes"][0]["synthetic_only"] is True
            assert changed["model_calls"] == 0
            assert changed["personal_tool_calls"] == 0

            user_wakes = await store.list_wakes(
                source_app="operly", kind="workspace",
                user_id="test-user", workspace_id="workspace-one",
                wait_id=personal["wait_id"],
            )
            assert len(user_wakes) == 1
            assert user_wakes[0]["status"] == "awaiting_authorization"
            assert user_wakes[0]["attempts"] == 0
            with pytest.raises(LookupError):
                await store.list_wakes(
                    source_app="operly", kind="workspace",
                    user_id="test-user", workspace_id="workspace-two",
                    wait_id=personal["wait_id"],
                )

            # Restart the worker's DB pool. Outbox wake and one-shot
            # subscription state must remain durable and idempotent.
            await pool.close()
            pool = await asyncpg.create_pool(
                dsn=dsn, min_size=1, max_size=4,
                server_settings={"search_path": schema},
            )
            store = EventWaitStore(pool)
            same = await check_web_watch(
                pool, "wikipedia_ai_updates", search=changed_search,
                now=change_at + timedelta(seconds=3),
            )
            assert same["status"] == "unchanged"
            assert same["event_published"] is False
            async with pool.acquire() as con:
                assert await con.fetchval(
                    "SELECT count(*) FROM dragonzpyder_event_inbox"
                ) == 1
                assert await con.fetchval(
                    "SELECT count(*) FROM dragonzpyder_event_wakes"
                ) == 2
            assert await store.drain_canary(
                now=change_at + timedelta(seconds=3)
            ) == []

            cancelled = await store.cancel(
                source_app="operly", kind="workspace",
                user_id="test-user", workspace_id="workspace-one",
                wait_id=personal["wait_id"],
            )
            assert cancelled["status"] == "cancelled"
            cancelled_wakes = await store.list_wakes(
                source_app="operly", kind="workspace",
                user_id="test-user", workspace_id="workspace-one",
                wait_id=personal["wait_id"],
            )
            assert cancelled_wakes[0]["status"] == "cancelled"

            # Empty or failed web search MUST NOT fabricate a change event.
            async def empty_search(*args, **kwargs):
                return {"results": []}
            no_results = await check_web_watch(
                pool, "wikipedia_ai_updates", search=empty_search,
                now=change_at + timedelta(seconds=604),
            )
            assert no_results["status"] == "no_results"
            assert no_results["event_published"] is False

        finally:
            if pool:
                await pool.close()
            try:
                await admin.execute('DROP SCHEMA IF EXISTS "' + schema + '" CASCADE')
            finally:
                await admin.close()

    asyncio.run(scenario())


@pytest.mark.skipif(not os.getenv("DRAGONZPYDER_BUDGET_TEST_DSN"),
                    reason="Requires disposable PostgreSQL")
def test_outdated_event_claim_cannot_complete_after_cancellation(monkeypatch):
    import asyncpg
    enable(monkeypatch)

    async def scenario():
        dsn = os.environ["DRAGONZPYDER_BUDGET_TEST_DSN"]
        schema = "dz_event_cancel_" + uuid4().hex
        admin = await asyncpg.connect(dsn)
        pool = None
        clock = datetime.now(timezone.utc).replace(microsecond=0)
        try:
            await admin.execute('CREATE SCHEMA "' + schema + '"')
            pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=2,
                                              server_settings={"search_path": schema})
            async with pool.acquire() as con:
                await con.execute(SCHEMA)
            await register_operator_watch(pool, monitor_id="watch_test_one",
                                          query="scientific research", now=clock)
            store = EventWaitStore(pool)
            wait = await store.subscribe(
                source_app="internal_canary", kind="personal",
                user_id="internal-staging-probe", workspace_id=None,
                request_id=str(uuid4()), monitor_id="watch_test_one",
            )
            async def old(*args, **kwargs):
                return source("Old", "https://en.wikipedia.org/wiki/Old")
            async def new(*args, **kwargs):
                return source("New", "https://en.wikipedia.org/wiki/New")
            await check_web_watch(pool, "watch_test_one", search=old, now=clock)
            change_at = clock + timedelta(seconds=610)
            result = await check_web_watch(pool, "watch_test_one", search=new,
                                           now=change_at)
            assert result["wakes_created"] == 1
            claim = await store.claim_canary(now=change_at)
            assert claim is not None
            await store.cancel(
                source_app="internal_canary", kind="personal",
                user_id="internal-staging-probe", workspace_id=None,
                wait_id=wait["wait_id"],
            )
            stale = await store.complete_canary(
                claim, now=change_at + timedelta(seconds=1)
            )
            assert stale["status"] == "not_committed"
            assert await store.claim_canary(
                now=change_at + timedelta(seconds=100)
            ) is None
        finally:
            if pool:
                await pool.close()
            try:
                await admin.execute('DROP SCHEMA IF EXISTS "' + schema + '" CASCADE')
            finally:
                await admin.close()

    asyncio.run(scenario())
