"""Twelve interval decisions with durable PostgreSQL and synthetic clock.

This is a zero-inference functional regression, NOT a real 60-minute Hatchet
schedule or a test of subjective model judgments.
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


class DeterministicTools:
    def __init__(self):
        self.ram = 35.0
        self.disk = 50.0
        self.calls = 0

    def invoke(self, name, arguments=None):
        self.calls += 1
        if name == "time.now":
            return {"utc": "2026-11-21T00:00:00+00:00", "unix_seconds": 1795219200}
        if name == "system.memory":
            return {"used_percent": self.ram, "scope": "container"}
        if name == "system.disk":
            return {"used_percent": self.disk, "scope": "worker_root"}
        raise AssertionError("Non-read-only tool invoked")


@pytest.mark.skipif(not os.getenv("DRAGONZPYDER_BUDGET_TEST_DSN"),
                    reason="Requires disposable PostgreSQL test database")
def test_twelve_distinct_monitor_buckets_duplicate_suppression_restart_and_decisions():
    import asyncpg

    async def scenario():
        dsn = os.environ["DRAGONZPYDER_BUDGET_TEST_DSN"]
        schema = "dz_horizon_" + uuid4().hex
        admin = await asyncpg.connect(dsn)
        pool = None
        try:
            await admin.execute(f'CREATE SCHEMA "{schema}"')
            async def connect():
                return await asyncpg.create_pool(
                    dsn=dsn, min_size=1, max_size=3,
                    server_settings={"search_path": schema},
                )
            pool = await connect()
            async with pool.acquire() as con:
                await con.execute(MONITOR_SCHEMA)
            tools = DeterministicTools()
            agent = LocalMonitorAgent(pool, registry=tools, policy=MonitorPolicy())
            t0 = datetime(2026, 11, 21, 8, 0, tzinfo=timezone.utc)
            ram = [35, 38, 50, 87, 90, 89, 88, 70, 69, 40, 85, 86]
            expected = [
                [], [], [], ["ram_high", "ram_jump"], ["ram_high"],
                ["ram_high"], ["ram_high"], [], ["disk_high"], [],
                ["ram_high", "ram_jump"], ["ram_high"],
            ]
            receipts = []
            for i in range(12):
                if i == 6:
                    # The same logical monitor is reconstructed on a new pool.
                    await pool.close()
                    pool = await connect()
                    agent = LocalMonitorAgent(pool, registry=tools, policy=MonitorPolicy())
                tools.ram = float(ram[i])
                tools.disk = 93.0 if i == 8 else 50.0
                now = t0 + timedelta(minutes=5 * i)
                before = tools.calls
                first = await agent.tick(now=now)
                assert first["new_observation"] is True
                assert first["alerts"] == expected[i]
                assert first["model_calls"] == 0
                assert first["external_tool_calls"] == 0
                assert tools.calls == before + 3
                same_bucket = await agent.tick(now=now + timedelta(seconds=15))
                assert same_bucket["new_observation"] is False
                assert same_bucket["receipt_sha256"] == first["receipt_sha256"]
                assert tools.calls == before + 3
                receipts.append(first["receipt_sha256"])
            assert len(set(receipts)) == 12
            async with pool.acquire() as con:
                count = await con.fetchval(
                    "SELECT count(*) FROM dragonzpyder_local_observations"
                )
                assert count == 12
        finally:
            if pool is not None:
                await pool.close()
            try:
                await admin.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            finally:
                await admin.close()

    asyncio.run(scenario())
