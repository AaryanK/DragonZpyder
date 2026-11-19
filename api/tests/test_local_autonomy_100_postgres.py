"""Real PostgreSQL 100-wakeup accelerated persistence and recovery stress.

Simulated clock and RAM/disk sensors: not 100 actual Hatchet cron fires.
No inference, network actions, or real device mutation.
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_platform.local_monitor import LocalMonitorAgent, MonitorPolicy, MONITOR_SCHEMA


class SimulatedLocalSensor:
    def __init__(self):
        self.ram = 30.0
        self.disk = 40.0
        self.clock = datetime(2026, 11, 19, 8, 0, tzinfo=timezone.utc)

    def invoke(self, name, arguments=None):
        assert arguments == {}
        if name == "time.now":
            return {"utc": self.clock.isoformat(), "unix_seconds": int(self.clock.timestamp())}
        if name == "system.memory":
            return {"scope": "container", "used_percent": self.ram,
                    "total_bytes": 1000, "used_bytes": int(self.ram * 10),
                    "available_bytes": int((100 - self.ram) * 10)}
        if name == "system.disk":
            return {"scope": "worker_root", "used_percent": self.disk,
                    "total_bytes": 1000, "used_bytes": int(self.disk * 10),
                    "free_bytes": int((100 - self.disk) * 10)}
        raise AssertionError("Unapproved local capability")


@pytest.mark.skipif(not os.getenv("DRAGONZPYDER_BUDGET_TEST_DSN"),
                    reason="Only an isolated disposable PostgreSQL database may be used")
def test_100_wakes_deduplicate_survive_restarts_and_persist_decisions():
    import asyncpg

    async def scenario():
        dsn = os.environ["DRAGONZPYDER_BUDGET_TEST_DSN"]
        schema = "dz_100wakes_" + uuid4().hex
        admin = await asyncpg.connect(dsn)
        pool = None
        try:
            await admin.execute(f'CREATE SCHEMA "{schema}"')

            async def reopen():
                return await asyncpg.create_pool(
                    dsn=dsn, min_size=1, max_size=4,
                    server_settings={"search_path": schema},
                )

            pool = await reopen()
            async with pool.acquire() as con:
                await con.execute(MONITOR_SCHEMA)
            sensors = SimulatedLocalSensor()
            start = sensors.clock
            receipts = set()
            attention_count = 0
            previous_ram = None
            for index in range(100):
                if index in (25, 50, 75):
                    await pool.close()
                    pool = await reopen()
                sensors.clock = start + timedelta(minutes=5 * index, seconds=12)
                sensors.ram = float(22 + (index % 20) * 4)
                sensors.disk = float(30 + (index % 17) * 4)
                agent = LocalMonitorAgent(pool, registry=sensors, policy=MonitorPolicy())
                if index % 11 == 0:
                    two = await asyncio.gather(
                        agent.tick(now=sensors.clock), agent.tick(now=sensors.clock)
                    )
                    assert sum(1 for row in two if row["new_observation"]) == 1
                    assert two[0]["receipt_sha256"] == two[1]["receipt_sha256"]
                    outcome = two[0]
                else:
                    outcome = await agent.tick(now=sensors.clock)
                    assert outcome["new_observation"] is True
                expected = []
                if sensors.ram >= 85:
                    expected.append("ram_high")
                if sensors.disk >= 90:
                    expected.append("disk_high")
                if previous_ram is not None and sensors.ram - previous_ram >= 15:
                    expected.append("ram_jump")
                previous_ram = sensors.ram
                assert outcome["status"] == ("attention" if expected else "healthy")
                assert outcome["alerts"] == expected
                assert outcome["model_calls"] == 0
                assert outcome["external_tool_calls"] == 0
                assert outcome["receipt_sha256"] not in receipts
                receipts.add(outcome["receipt_sha256"])
                attention_count += bool(expected)
                assert (await agent.tick(now=sensors.clock))["new_observation"] is False
            assert 0 < attention_count < 100
            async with pool.acquire() as con:
                rows = await con.fetch(
                    """SELECT bucket_start,receipt_sha256
                       FROM dragonzpyder_local_observations
                       WHERE monitor_key='worker-health'
                       ORDER BY bucket_start"""
                )
            assert len(rows) == 100
            assert len({r["bucket_start"] for r in rows}) == 100
            assert len({r["receipt_sha256"] for r in rows}) == 100
            assert {r["receipt_sha256"] for r in rows} == receipts
        finally:
            if pool is not None:
                await pool.close()
            try:
                await admin.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            finally:
                await admin.close()

    asyncio.run(scenario())
