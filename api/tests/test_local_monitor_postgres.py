"""Real disposable PostgreSQL proof: persisted state, restart, duplicate wake.

No paid inference or external effects. Runs against CI's temporary database.
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_platform.local_monitor import LocalMonitorAgent, MonitorPolicy, MONITOR_SCHEMA


class FakeLocalTools:
    def __init__(self):
        self.calls = []
        self.ram = 35.0
        self.disk = 40.0

    def invoke(self, name, args=None):
        self.calls.append(name)
        if name == "time.now":
            return {"utc": "2026-11-19T08:00:00+00:00", "unix_seconds": 1795075200}
        if name == "system.memory":
            return {"scope": "container", "total_bytes": 1000,
                    "used_bytes": int(self.ram * 10),
                    "available_bytes": int((100 - self.ram) * 10),
                    "used_percent": self.ram}
        if name == "system.disk":
            return {"scope": "worker_root", "total_bytes": 1000,
                    "used_bytes": int(self.disk * 10),
                    "free_bytes": int((100 - self.disk) * 10),
                    "used_percent": self.disk}
        raise AssertionError("Unexpected tool")


@pytest.mark.skipif(not os.getenv("DRAGONZPYDER_BUDGET_TEST_DSN"),
                    reason="Requires disposable PostgreSQL test database")
def test_monitor_survives_restart_and_has_exactly_one_log_per_interval():
    import asyncpg

    async def scenario():
        dsn = os.environ["DRAGONZPYDER_BUDGET_TEST_DSN"]
        schema = "dz_monitor_" + uuid4().hex
        admin = await asyncpg.connect(dsn)
        pool = None
        try:
            await admin.execute(f'CREATE SCHEMA "{schema}"')
            pool = await asyncpg.create_pool(
                dsn=dsn, min_size=1, max_size=4,
                server_settings={"search_path": schema},
            )
            async with pool.acquire() as con:
                await con.execute(MONITOR_SCHEMA)
            tools = FakeLocalTools()
            agent = LocalMonitorAgent(pool, registry=tools, policy=MonitorPolicy())
            start = datetime(2026, 11, 19, 8, 0, 22, tzinfo=timezone.utc)
            initial = await agent.tick(now=start)
            assert initial["status"] == "healthy"
            assert initial["new_observation"] is True
            assert initial["model_calls"] == 0
            assert len(tools.calls) == 3
            replay = await agent.tick(now=start + timedelta(seconds=10))
            assert replay["receipt_sha256"] == initial["receipt_sha256"]
            assert replay["new_observation"] is False
            assert len(tools.calls) == 3

            # Simulated worker death: discard pool and reconstruct agent.
            await pool.close()
            pool = await asyncpg.create_pool(
                dsn=dsn, min_size=1, max_size=4,
                server_settings={"search_path": schema},
            )
            recovered = LocalMonitorAgent(pool, registry=tools)
            assert (await recovered.tick(now=start))["new_observation"] is False
            tools.ram = 89.0
            tools.disk = 96.0
            wake = start + timedelta(minutes=5)
            results = await asyncio.gather(
                recovered.tick(now=wake), recovered.tick(now=wake)
            )
            assert sum(int(r["new_observation"]) for r in results) == 1
            assert all(r["status"] == "attention" for r in results)
            assert all(r["alerts"] == ["ram_high", "disk_high", "ram_jump"] for r in results)
            assert all(r["receipt_sha256"] == results[0]["receipt_sha256"] for r in results)
            async with pool.acquire() as con:
                assert await con.fetchval(
                    "SELECT count(*) FROM dragonzpyder_local_observations"
                ) == 2
            separate = await recovered.tick(monitor_key="other-worker", now=start)
            assert separate["new_observation"] is True
        finally:
            if pool is not None:
                await pool.close()
            try:
                await admin.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            finally:
                await admin.close()

    asyncio.run(scenario())
