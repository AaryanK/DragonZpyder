"""Disposable PostgreSQL proof of 3 real scheduled goal steps across restarts.

Uses model-shaped fake AIMessage tool calls. This is NOT a paid LLM run.
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_platform.persistent_tool_canary import (
    GOAL_ID, PersistentToolCanary, SCHEMA,
)


class Model:
    def __init__(self):
        self.calls = 0
        self.names = ()

    def bind_tools(self, specs, tool_choice):
        assert tool_choice == "required"
        self.names = tuple(spec["function"]["name"] for spec in specs)
        return self

    async def ainvoke(self, messages):
        self.calls += 1
        assert messages[-1]["role"] == "user"
        # Choose among tools still offered by actual persisted run state.
        return SimpleNamespace(tool_calls=[{"name": self.names[-1], "args": {}}])


class StubLocalTools:
    def __init__(self):
        self.calls = []

    def invoke(self,name,args):
        assert args == {}
        self.calls.append(name)
        return {"test_sensor": name, "signal":len(self.calls), "used_percent": 40}


@pytest.mark.skipif(not os.getenv("DRAGONZPYDER_BUDGET_TEST_DSN"),
                    reason="Requires disposable PostgreSQL")
def test_three_wakes_resume_across_new_database_pool_and_deduplicate():
    import asyncpg

    async def run():
        dsn=os.environ["DRAGONZPYDER_BUDGET_TEST_DSN"]
        namespace="dz_horizon_" + uuid4().hex
        admin=await asyncpg.connect(dsn)
        pool=None
        try:
            await admin.execute(f'CREATE SCHEMA "{namespace}"')
            async def open_pool():
                return await asyncpg.create_pool(dsn, min_size=1, max_size=4,
                    server_settings={"search_path":namespace}, command_timeout=90)
            pool=await open_pool()
            async with pool.acquire() as con:
                await con.execute(SCHEMA)
                await con.execute(
                    "INSERT INTO dz_staging_long_horizon_goals(id) VALUES($1)",
                    GOAL_ID,
                )
            model=Model()
            tools=StubLocalTools()
            start=datetime(2026,11,19,9,0,15,tzinfo=timezone.utc)

            first=PersistentToolCanary(pool,model=model,registry=tools)
            result=await first.wake(now=start)
            assert result["state"] == "active"
            assert result["next_step"] == 1
            assert result["model_calls"] == 1
            replay=await first.wake(now=start+timedelta(seconds=15))
            assert replay["reason"] == "same_interval"
            assert replay["tool_calls"] == 0
            assert model.calls == 1

            # Restart worker: checkpoint lives in Postgres, not process memory.
            await pool.close()
            pool=await open_pool()
            second=PersistentToolCanary(pool,model=model,registry=tools)
            t2=start+timedelta(minutes=5)
            race=await asyncio.gather(second.wake(now=t2),second.wake(now=t2))
            assert sorted(x["tool_calls"] for x in race) == [0,1]
            assert model.calls == 2

            await pool.close()
            pool=await open_pool()
            third=PersistentToolCanary(pool,model=model,registry=tools)
            result=await third.wake(now=start+timedelta(minutes=10))
            assert result["state"] == "completed"
            assert result["next_step"] == 3
            assert result["verification"] == "database_readback"
            assert (await third.wake(now=start+timedelta(minutes=15)))["reason"] == "terminal"
            assert model.calls == 3
            assert len(tools.calls) == 3
            assert set(tools.calls) == {"time.now", "system.memory", "system.disk"}

            async with pool.acquire() as con:
                receipts=await con.fetch(
                    """SELECT step_index,tool_name,result_sha256,bucket_start
                       FROM dz_staging_long_horizon_receipts ORDER BY step_index"""
                )
                goal=await con.fetchrow(
                    "SELECT next_step,state FROM dz_staging_long_horizon_goals WHERE id=$1",
                    GOAL_ID,
                )
                assert len(receipts) == 3
                assert [row["step_index"] for row in receipts] == [0,1,2]
                assert len({row["bucket_start"] for row in receipts}) == 3
                assert len({row["tool_name"] for row in receipts}) == 3
                assert all(len(row["result_sha256"]) == 64 for row in receipts)
                assert goal["next_step"] == 3 and goal["state"] == "completed"
        finally:
            if pool:
                await pool.close()
            try:
                await admin.execute(f'DROP SCHEMA IF EXISTS "{namespace}" CASCADE')
            finally:
                await admin.close()
    asyncio.run(run())


@pytest.mark.skipif(not os.getenv("DRAGONZPYDER_BUDGET_TEST_DSN"),
                    reason="Requires disposable PostgreSQL")
def test_cancelled_goal_does_not_invoke_model_or_tool():
    import asyncpg

    async def run():
        dsn=os.environ["DRAGONZPYDER_BUDGET_TEST_DSN"]
        namespace="dz_cancel_" + uuid4().hex
        admin=await asyncpg.connect(dsn)
        pool=None
        try:
            await admin.execute(f'CREATE SCHEMA "{namespace}"')
            pool=await asyncpg.create_pool(dsn,min_size=1,max_size=2,
                server_settings={"search_path":namespace})
            async with pool.acquire() as con:
                await con.execute(SCHEMA)
                await con.execute(
                    "INSERT INTO dz_staging_long_horizon_goals(id,state) VALUES($1,'cancelled')",GOAL_ID)
            model=Model()
            tools=StubLocalTools()
            result=await PersistentToolCanary(pool,model=model,registry=tools).wake()
            assert result["state"] == "cancelled"
            assert model.calls == 0 and tools.calls == []
        finally:
            if pool: await pool.close()
            try: await admin.execute(f'DROP SCHEMA IF EXISTS "{namespace}" CASCADE')
            finally: await admin.close()
    asyncio.run(run())


@pytest.mark.skipif(not os.getenv("DRAGONZPYDER_BUDGET_TEST_DSN"),
                    reason="Requires disposable PostgreSQL")
def test_tampered_historical_receipt_fails_closed_before_model_or_tool():
    """A restarted worker must reject altered JSONB even with an intact digest."""
    import asyncpg
    from agent_platform.persistent_tool_canary import CanaryError

    async def run():
        dsn = os.environ["DRAGONZPYDER_BUDGET_TEST_DSN"]
        namespace = "dz_tamper_" + uuid4().hex
        admin = await asyncpg.connect(dsn)
        pool = None
        try:
            await admin.execute(f'CREATE SCHEMA "{namespace}"')
            async def open_pool():
                return await asyncpg.create_pool(
                    dsn, min_size=1, max_size=2,
                    server_settings={"search_path": namespace})
            pool = await open_pool()
            async with pool.acquire() as con:
                await con.execute(SCHEMA)
                await con.execute(
                    "INSERT INTO dz_staging_long_horizon_goals(id) VALUES($1)",
                    GOAL_ID)
            start = datetime(2026, 11, 19, 9, 0, 15, tzinfo=timezone.utc)
            model, tools = Model(), StubLocalTools()
            first = await PersistentToolCanary(
                pool, model=model, registry=tools).wake(now=start)
            assert first["next_step"] == 1
            await pool.close()
            pool = await open_pool()
            async with pool.acquire() as con:
                await con.execute(
                    """UPDATE dz_staging_long_horizon_receipts
                       SET result_json='{"tampered":true}'::jsonb
                       WHERE goal_id=$1 AND step_index=0""", GOAL_ID)
            with pytest.raises(CanaryError, match="content integrity"):
                await PersistentToolCanary(
                    pool, model=model, registry=tools).wake(
                        now=start + timedelta(minutes=5))
            assert model.calls == 1
            assert len(tools.calls) == 1
            async with pool.acquire() as con:
                goal = await con.fetchrow(
                    "SELECT next_step,state FROM dz_staging_long_horizon_goals WHERE id=$1",
                    GOAL_ID)
                assert goal["next_step"] == 1 and goal["state"] == "active"
                assert await con.fetchval(
                    "SELECT count(*) FROM dz_staging_long_horizon_receipts WHERE goal_id=$1",
                    GOAL_ID) == 1
        finally:
            if pool:
                await pool.close()
            try:
                await admin.execute(f'DROP SCHEMA IF EXISTS "{namespace}" CASCADE')
            finally:
                await admin.close()
    asyncio.run(run())
