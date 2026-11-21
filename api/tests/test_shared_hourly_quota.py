"""Shared inference admission never falls back to an unsafe process-local budget."""
import asyncio
import sys
from pathlib import Path

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from usage_ledger import UsageLedger, SCHEMA


class Connection:
    def __init__(self, permitted):
        self.permitted = permitted
        self.calls = []

    async def fetchrow(self, sql, limit):
        self.calls.append((sql, limit))
        assert "ON CONFLICT(bucket) DO UPDATE" in sql
        assert "WHERE agent_hourly_call_budget.call_count < $1" in sql
        return {"call_count": 1} if self.permitted else None


class Acquire:
    def __init__(self, con):
        self.con = con

    async def __aenter__(self):
        return self.con

    async def __aexit__(self, exc_type, exc, tb):
        return False


class Pool:
    def __init__(self, con):
        self.con = con

    def acquire(self):
        return Acquire(self.con)


def test_shared_hourly_admission_uses_atomic_conditional_upsert():
    assert "CREATE TABLE IF NOT EXISTS agent_hourly_call_budget" in SCHEMA
    for permitted in (True, False):
        ledger = UsageLedger()
        con = Connection(permitted)
        ledger.pool = Pool(con)
        assert asyncio.run(ledger.charge_agent_hour(120)) is permitted
        assert len(con.calls) == 1
        assert con.calls[0][1] == 120


def test_shared_hourly_admission_fails_closed_without_database():
    ledger = UsageLedger()
    with pytest.raises(RuntimeError, match="requires PostgreSQL"):
        asyncio.run(ledger.charge_agent_hour(120))
    for invalid in (0, 1001, 1.5, True, -1):
        with pytest.raises(ValueError):
            asyncio.run(ledger.charge_agent_hour(invalid))


def test_shared_hourly_admission_does_not_hide_database_errors():
    ledger = UsageLedger()
    class Unavailable:
        def acquire(self):
            raise RuntimeError("database unavailable")
    ledger.pool = Unavailable()
    with pytest.raises(RuntimeError, match="database unavailable"):
        asyncio.run(ledger.charge_agent_hour(120))
