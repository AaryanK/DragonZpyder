"""Real PostgreSQL concurrency/restart contracts for the UNWIRED budget store.

Requires DRAGONZPYDER_BUDGET_TEST_DSN pointing to a disposable test DB.
No paid model calls. Isolated schema is created and dropped in finally.
"""
import asyncio
import os
from decimal import Decimal
from pathlib import Path
import sys
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_platform.budget_reservations import AtomicBudgetStore, BudgetExceeded, SCHEMA


@pytest.mark.skipif(not os.getenv("DRAGONZPYDER_BUDGET_TEST_DSN"),
                    reason="Requires explicitly configured disposable PostgreSQL")
def test_real_postgres_atomic_parallel_reservations_and_restart():
    import asyncpg

    async def scenario():
        dsn = os.environ["DRAGONZPYDER_BUDGET_TEST_DSN"]
        # A fresh, isolated schema prevents writes to existing app tables.
        schema = "dz_budget_test_" + uuid4().hex
        admin = await asyncpg.connect(dsn)
        pool = None
        try:
            await admin.execute('CREATE SCHEMA "' + schema + '"')
            pool = await asyncpg.create_pool(
                dsn=dsn, min_size=2, max_size=8,
                server_settings={"search_path": schema},
            )
            async with pool.acquire() as con:
                await con.execute(SCHEMA)
            store = AtomicBudgetStore(pool)
            job, tenant = str(uuid4()), "test-tenant"
            await store.create_job(job_id=job, tenant_id=tenant, ceiling_usd="1")
            requests = [str(uuid4()) for _ in range(8)]

            async def reserve(request):
                try:
                    return await store.reserve(
                        job_id=job, tenant_id=tenant, request_id=request,
                        estimate_usd="0.30")
                except BudgetExceeded:
                    return "exceeded"

            results = await asyncio.gather(*(reserve(req) for req in requests))
            assert results.count(True) == 3, results
            assert results.count("exceeded") == 5, results
            async with pool.acquire() as con:
                parent = await con.fetchrow(
                    "SELECT reserved_usd,settled_usd FROM agent_job_budgets WHERE job_id=$1",
                    __import__("uuid").UUID(job),
                )
            assert parent["reserved_usd"] == Decimal("0.9")
            assert parent["settled_usd"] == 0

            # New store object simulates process restart; old request cannot
            # reserve or reissue paid work even after settlement.
            restarted = AtomicBudgetStore(pool)
            successful = [req for req, result in zip(requests, results) if result is True]
            assert await restarted.reserve(
                job_id=job, tenant_id=tenant, request_id=successful[0],
                estimate_usd="0.30") is False
            with pytest.raises(BudgetExceeded, match="hold retained"):
                await restarted.settle(
                    job_id=job, tenant_id=tenant, request_id=successful[0],
                    actual_usd=None)
            async with pool.acquire() as con:
                hold = await con.fetchrow(
                    "SELECT status,actual_usd FROM agent_budget_reservations "
                    "WHERE request_id=$1",
                    __import__("uuid").UUID(successful[0]),
                )
                parent = await con.fetchrow(
                    "SELECT reserved_usd,settled_usd FROM agent_job_budgets "
                    "WHERE job_id=$1",
                    __import__("uuid").UUID(job),
                )
            assert hold["status"] == "unknown"
            assert hold["actual_usd"] is None
            assert parent["reserved_usd"] == Decimal("0.9")
            assert parent["settled_usd"] == 0
            assert await restarted.settle(
                job_id=job, tenant_id=tenant, request_id=successful[0],
                actual_usd="0.10") is True
            assert await restarted.settle(
                job_id=job, tenant_id=tenant, request_id=successful[0],
                actual_usd="0.10") is False
            with pytest.raises(BudgetExceeded, match="Conflicting settlement"):
                await restarted.settle(
                    job_id=job, tenant_id=tenant, request_id=successful[0],
                    actual_usd="0.20")
            assert await restarted.reserve(
                job_id=job, tenant_id=tenant, request_id=str(uuid4()),
                estimate_usd="0.30") is True
            async with pool.acquire() as con:
                parent = await con.fetchrow(
                    "SELECT reserved_usd,settled_usd,ceiling_usd "
                    "FROM agent_job_budgets WHERE job_id=$1",
                    __import__("uuid").UUID(job),
                )
            assert parent["reserved_usd"] == Decimal("0.9")
            assert parent["settled_usd"] == Decimal("0.1")
            assert parent["reserved_usd"] + parent["settled_usd"] == parent["ceiling_usd"]
        finally:
            if pool is not None:
                await pool.close()
            try:
                await admin.execute('DROP SCHEMA IF EXISTS "' + schema + '" CASCADE')
            finally:
                await admin.close()

    asyncio.run(scenario())


@pytest.mark.skipif(not os.getenv("DRAGONZPYDER_BUDGET_TEST_DSN"),
                    reason="Requires explicitly configured disposable PostgreSQL")
def test_real_postgres_cross_tenant_and_ceiling_replay_rejected():
    import asyncpg

    async def scenario():
        dsn = os.environ["DRAGONZPYDER_BUDGET_TEST_DSN"]
        schema = "dz_budget_test_" + uuid4().hex
        admin = await asyncpg.connect(dsn)
        pool = None
        try:
            await admin.execute('CREATE SCHEMA "' + schema + '"')
            pool = await asyncpg.create_pool(
                dsn=dsn, min_size=1, max_size=3,
                server_settings={"search_path": schema},
            )
            async with pool.acquire() as con:
                await con.execute(SCHEMA)
            store = AtomicBudgetStore(pool)
            job, request = str(uuid4()), str(uuid4())
            await store.create_job(job_id=job, tenant_id="owner", ceiling_usd="0.5")
            with pytest.raises(BudgetExceeded):
                await store.create_job(job_id=job, tenant_id="owner", ceiling_usd="5")
            with pytest.raises(BudgetExceeded):
                await store.create_job(job_id=job, tenant_id="other", ceiling_usd="0.5")
            with pytest.raises(BudgetExceeded):
                await store.reserve(
                    job_id=job, tenant_id="other", request_id=request,
                    estimate_usd="0.1")
            assert await store.reserve(
                job_id=job, tenant_id="owner", request_id=request,
                estimate_usd="0.1")
            with pytest.raises(BudgetExceeded):
                await store.settle(
                    job_id=job, tenant_id="other", request_id=request,
                    actual_usd="0")
        finally:
            if pool is not None:
                await pool.close()
            try:
                await admin.execute('DROP SCHEMA IF EXISTS "' + schema + '" CASCADE')
            finally:
                await admin.close()

    asyncio.run(scenario())
