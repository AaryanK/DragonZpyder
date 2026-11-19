"""Durable multi-wake/restart test against CI's disposable real PostgreSQL."""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_platform.horizon_agent import GOAL, SCHEMA, tick


class Telemetry:
    def __init__(self):
        self.calls = []

    def invoke(self, name, args=None):
        assert args == {}
        self.calls.append(name)
        return {"tool": name, "sample": 42, "scope": "test-worker"}


@pytest.mark.skipif(not os.getenv("DRAGONZPYDER_BUDGET_TEST_DSN"),
                    reason="Requires disposable PostgreSQL CI service")
def test_three_distinct_scheduled_wakes_resume_from_pg_and_finish_once(monkeypatch):
    import asyncpg

    async def check():
        monkeypatch.setenv("DRAGONZPYDER_STAGE", "staging")
        monkeypatch.setenv("DRAGONZPYDER_HORIZON_CANARY_ENABLED", "1")
        monkeypatch.setenv("DRAGONZPYDER_HORIZON_DATABASE_URL",
                           "postgresql://not-used-by-fake-selector/test")
        monkeypatch.setenv("DRAGONZPYDER_AGENT_GATEWAY_BASE_URL",
                           "http://dragonzpyder-gateway.railway.internal:8080/internal/agent/v1")
        monkeypatch.setenv("DRAGONZPYDER_AGENT_GATEWAY_TOKEN", "x" * 48)
        monkeypatch.setenv("DRAGONZPYDER_HORIZON_MODEL_ID", "openai/gpt-oss-120b")
        monkeypatch.setenv("DRAGONZPYDER_RUNTIME_ALLOWED_MODELS", "openai/gpt-oss-120b")
        schema = "dz_horizon_" + uuid4().hex
        dsn = os.environ["DRAGONZPYDER_BUDGET_TEST_DSN"]
        admin = await asyncpg.connect(dsn)
        pool = None
        telemetry = Telemetry()
        model_choices = []

        async def choose(base, model, *, already):
            available = [x for x in ("time.now", "system.memory", "system.disk")
                         if x not in already]
            model_choices.append((model, frozenset(already)))
            return available[0]

        async def reopen():
            return await asyncpg.create_pool(
                dsn=dsn, min_size=1, max_size=4,
                server_settings={"search_path": schema},
            )

        try:
            await admin.execute(f'CREATE SCHEMA "{schema}"')
            pool = await reopen()
            async with pool.acquire() as con:
                await con.execute(SCHEMA)
            clock = datetime(2026, 11, 19, 10, 0, tzinfo=timezone.utc)
            first = await tick(pool, now=clock, selector=choose, local_registry=telemetry)
            assert first["status"] == "progress"
            assert first["completed_steps"] == 1
            assert first["model_selected"] is True
            assert (await tick(pool, now=clock + timedelta(minutes=1),
                               selector=choose, local_registry=telemetry))["status"] == "waiting"
            # A process restart: the in-memory model/tools lose their state.
            await pool.close()
            pool = await reopen()
            second = await tick(pool, now=clock + timedelta(minutes=5),
                                selector=choose, local_registry=telemetry)
            assert second["status"] == "progress"
            assert second["completed_steps"] == 2
            await pool.close()
            pool = await reopen()
            third = await tick(pool, now=clock + timedelta(minutes=10),
                               selector=choose, local_registry=telemetry)
            assert third["status"] == "completed"
            assert third["completed_steps"] == 3
            replay = await tick(pool, now=clock + timedelta(minutes=15),
                                selector=choose, local_registry=telemetry)
            assert replay["status"] == "completed"
            assert replay["new_step"] is False
            assert telemetry.calls == ["time.now", "system.memory", "system.disk"]
            assert len(model_choices) == 3
            async with pool.acquire() as con:
                rows = await con.fetch(
                    "SELECT tool_name,model_selected FROM dz_staging_horizon_receipts_v1 ORDER BY step_index"
                )
                assert [r["tool_name"] for r in rows] == telemetry.calls
                assert all(r["model_selected"] for r in rows)
                assert await con.fetchval(
                    "SELECT step_index FROM dz_staging_horizon_v1 WHERE goal_key=$1", GOAL
                ) == 3
            assert len({first["tool_result_sha256"], second["tool_result_sha256"],
                        third["tool_result_sha256"]}) == 3
        finally:
            if pool is not None:
                await pool.close()
            await admin.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            await admin.close()

    asyncio.run(check())
