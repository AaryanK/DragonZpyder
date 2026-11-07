"""Offline invariants for an UNWIRED transactional budget primitive.

These do not prove PostgreSQL isolation or gateway integration. A dedicated
real-database concurrency/restart test is required before enabling fan-out.
"""
import asyncio
from decimal import Decimal
from pathlib import Path
import sys
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_platform.budget_reservations import (
    amount, nonnegative_amount, identity, AtomicBudgetStore, BudgetExceeded, SCHEMA,
)


@pytest.mark.parametrize("bad", [
    0, 0.1, True, None, "", "nan", "NaN", "Infinity", "-1", "0",
    "0.00000000001", "1000001", "1e1000",
])
def test_invalid_reservation_amounts_fail_closed(bad):
    with pytest.raises(ValueError):
        amount(bad)


def test_exact_decimal_quantization_and_free_settlement():
    assert amount("0.125") == Decimal("0.1250000000")
    assert nonnegative_amount("0") == Decimal("0E-10")
    with pytest.raises(ValueError):
        nonnegative_amount("-0.01")


def test_canonical_identities():
    key = str(uuid4())
    assert str(identity(key)) == key
    with pytest.raises(ValueError):
        identity(key.upper())


def test_schema_has_parent_ceiling_and_unique_idempotency_key():
    assert "request_id uuid PRIMARY KEY" in SCHEMA
    assert "reserved_usd + settled_usd <= ceiling_usd" in SCHEMA
    assert "job_id uuid PRIMARY KEY" in SCHEMA


class Transaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class Acquire(Transaction):
    def __init__(self, con):
        self.con = con

    async def __aenter__(self):
        return self.con


class FakeConnection:
    def __init__(self, ceiling="1"):
        self.ceiling = Decimal(ceiling)
        self.reserved = Decimal("0")
        self.settled = Decimal("0")
        self.reservations = {}
        self.statements = []

    def transaction(self):
        return Transaction()

    async def fetchrow(self, sql, *args):
        self.statements.append(sql)
        if "FROM agent_job_budgets" in sql:
            return {"ceiling_usd": self.ceiling,
                    "reserved_usd": self.reserved, "settled_usd": self.settled}
        if "FROM agent_budget_reservations" in sql:
            if "SELECT job_id,tenant_id" in sql:
                return self.reservations.get(args[0])
            entry = self.reservations.get(args[0])
            return None if entry is None else {k: entry[k]
                for k in ("estimate_usd", "actual_usd", "status")}
        raise AssertionError(sql)

    async def execute(self, sql, *args):
        self.statements.append(sql)
        if "INSERT INTO agent_budget_reservations" in sql:
            req, job, tenant, estimate = args
            self.reservations[req] = {
                "job_id": job, "tenant_id": tenant,
                "estimate_usd": estimate, "actual_usd": None,
                "status": "reserved",
            }
        elif "SET reserved_usd=reserved_usd+$3" in sql:
            self.reserved += args[2]
        elif "SET reserved_usd=reserved_usd-$3" in sql:
            self.reserved -= args[2]
            self.settled += args[3]
        elif "SET status='settled'" in sql:
            self.reservations[args[0]]["status"] = "settled"
            self.reservations[args[0]]["actual_usd"] = args[1]
        else:
            raise AssertionError(sql)


class Pool:
    def __init__(self, con):
        self.con = con

    def acquire(self):
        return Acquire(self.con)


def test_reservation_replay_ceiling_and_settlement():
    con = FakeConnection("0.60")
    store = AtomicBudgetStore(Pool(con))
    job, tenant, req1, req2 = str(uuid4()), "tenant", str(uuid4()), str(uuid4())

    async def scenario():
        assert await store.reserve(
            job_id=job, tenant_id=tenant, request_id=req1,
            estimate_usd="0.40") is True
        assert await store.reserve(
            job_id=job, tenant_id=tenant, request_id=req1,
            estimate_usd="0.40") is False
        with pytest.raises(BudgetExceeded, match="Conflicting idempotency"):
            await store.reserve(
                job_id=job, tenant_id=tenant, request_id=req1,
                estimate_usd="0.30")
        with pytest.raises(BudgetExceeded, match="exceeded"):
            await store.reserve(
                job_id=job, tenant_id=tenant, request_id=req2,
                estimate_usd="0.30")
        with pytest.raises(BudgetExceeded, match="hold retained"):
            await store.settle(
                job_id=job, tenant_id=tenant, request_id=req1,
                actual_usd=None)
        assert con.reserved == Decimal("0.40")
        assert await store.settle(
            job_id=job, tenant_id=tenant, request_id=req1,
            actual_usd="0.10") is True
        assert await store.settle(
            job_id=job, tenant_id=tenant, request_id=req1,
            actual_usd="0.10") is False
        with pytest.raises(BudgetExceeded, match="Conflicting settlement"):
            await store.settle(
                job_id=job, tenant_id=tenant, request_id=req1,
                actual_usd="0.20")
        assert con.reserved == 0 and con.settled == Decimal("0.10")
        assert await store.reserve(
            job_id=job, tenant_id=tenant, request_id=req2,
            estimate_usd="0.30") is True
        assert await store.settle(
            job_id=job, tenant_id=tenant, request_id=req2,
            actual_usd="0") is True
    asyncio.run(scenario())
    assert all("FOR UPDATE" in sql for sql in con.statements
               if "FROM agent_job_budgets" in sql)
