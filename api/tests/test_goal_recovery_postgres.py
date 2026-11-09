"""Recovery tests with a real throwaway PostgreSQL schema.

These exercise DB-only autonomous execution, cross-tenant hold, duplicate
Hatchet ticks, worker death after claim, expired leases, and cancellation.
No provider/model/tool integration is used in the test path.
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet

from agent_platform.goal_reconciler import GoalReconciler
from agent_platform.goal_store import DurableGoalStore, SCHEMA


@pytest.mark.skipif(not os.getenv("DRAGONZPYDER_BUDGET_TEST_DSN"),
                    reason="Requires disposable PostgreSQL test database")
def test_scheduled_goal_survives_worker_restart_and_never_executes_a_user_tool():
    import asyncpg

    async def scenario():
        schema = "dz_resume_" + uuid4().hex
        dsn = os.environ["DRAGONZPYDER_BUDGET_TEST_DSN"]
        admin = await asyncpg.connect(dsn)
        pool = None
        try:
            await admin.execute('CREATE SCHEMA "' + schema + '"')
            pool = await asyncpg.create_pool(
                dsn=dsn, min_size=1, max_size=4,
                server_settings={"search_path": schema},
            )
            async with pool.acquire() as con:
                await con.execute(SCHEMA)
            store = DurableGoalStore(pool, encryption_key=Fernet.generate_key().decode())
            clock = datetime.now(timezone.utc).replace(microsecond=0)
            due = clock - timedelta(seconds=5)
            schedule = {"type": "interval", "every_seconds": 600}

            probe = await store.register(
                source_app="dragonzpyder", kind="personal",
                user_id="internal-staging-probe", workspace_id=None,
                request_id=str(uuid4()), goal="NO EXTERNAL EXECUTION",
                schedule=schedule,
            )
            real_user = await store.register(
                source_app="operly", kind="workspace", user_id="person-1",
                workspace_id="team-1", request_id=str(uuid4()),
                goal="User goal needs fresh OAuth and authorization",
                schedule=schedule,
            )
            async with pool.acquire() as con:
                await con.execute(
                    """UPDATE dragonzpyder_goals SET next_run_at=$1
                       WHERE goal_id = ANY($2::uuid[])""",
                    due, [UUID(probe["goal_id"]), UUID(real_user["goal_id"])],
                )

            tick = GoalReconciler(pool)
            first = await tick.tick(now=clock)
            assert first["scheduled"] == {"pending": 1, "awaiting_authorization": 1}
            assert first["model_calls"] == 0
            assert first["personal_tool_calls"] == 0
            assert len(first["probes"]) == 1
            receipt = first["probes"][0]
            assert receipt["status"] == "completed"
            assert receipt["objective_verified"] is False
            assert receipt["synthetic_only"] is True
            assert len(receipt["evidence_sha256"]) == 64

            user_runs = await store.list_runs(
                source_app="operly", kind="workspace", user_id="person-1",
                workspace_id="team-1", goal_id=real_user["goal_id"],
            )
            assert len(user_runs) == 1
            assert user_runs[0]["status"] == "awaiting_authorization"
            assert user_runs[0]["attempts"] == 0
            with pytest.raises(LookupError):
                await store.list_runs(
                    source_app="operly", kind="workspace", user_id="person-1",
                    workspace_id="another-team", goal_id=real_user["goal_id"],
                )

            repeat = await tick.tick(now=clock)
            assert repeat["scheduled"] == {"pending": 0, "awaiting_authorization": 0}
            assert repeat["probes"] == []
            assert len(await store.list_runs(
                source_app="dragonzpyder", kind="personal",
                user_id="internal-staging-probe", workspace_id=None,
                goal_id=probe["goal_id"],
            )) == 1

            second_clock = clock + timedelta(seconds=600)
            second = await tick.enqueue_due(now=second_clock)
            assert second["pending"] == 1
            one, two = await asyncio.gather(
                tick.claim_probe(now=second_clock), tick.claim_probe(now=second_clock)
            )
            claims = [x for x in (one, two) if x is not None]
            assert len(claims) == 1
            first_claim = claims[0]
            assert first_claim["attempts"] == 1

            # Simulate a SIGKILL after claiming and before committing evidence.
            await pool.close()
            pool = await asyncpg.create_pool(
                dsn=dsn, min_size=1, max_size=4,
                server_settings={"search_path": schema},
            )
            recovered = GoalReconciler(pool)
            assert await recovered.claim_probe(
                now=second_clock + timedelta(seconds=10)
            ) is None
            retry_claim = await recovered.claim_probe(
                now=second_clock + timedelta(seconds=91)
            )
            assert retry_claim is not None
            assert retry_claim["run_id"] == first_claim["run_id"]
            assert retry_claim["attempts"] == 2
            old_attempt = await recovered.complete_probe(
                first_claim, now=second_clock + timedelta(seconds=92)
            )
            assert old_attempt["status"] == "not_committed"
            confirmed = await recovered.complete_probe(
                retry_claim, now=second_clock + timedelta(seconds=92)
            )
            assert confirmed["status"] == "completed"
            assert confirmed["attempts"] == 2

            store = DurableGoalStore(pool, encryption_key=Fernet.generate_key().decode())
            cancelled = await store.cancel(
                source_app="dragonzpyder", kind="personal",
                user_id="internal-staging-probe", workspace_id=None,
                goal_id=probe["goal_id"],
            )
            assert cancelled["status"] == "cancelled"
            next_tick = await recovered.tick(now=clock + timedelta(days=1))
            assert next_tick["scheduled"]["pending"] == 0
            assert next_tick["probes"] == []

            user_cancelled = await store.cancel(
                source_app="operly", kind="workspace",
                user_id="person-1", workspace_id="team-1",
                goal_id=real_user["goal_id"],
            )
            assert user_cancelled["status"] == "cancelled"
            after = await store.list_runs(
                source_app="operly", kind="workspace",
                user_id="person-1", workspace_id="team-1",
                goal_id=real_user["goal_id"],
            )
            assert all(x["status"] == "cancelled" for x in after)
        finally:
            if pool:
                await pool.close()
            try:
                await admin.execute('DROP SCHEMA IF EXISTS "' + schema + '" CASCADE')
            finally:
                await admin.close()

    asyncio.run(scenario())
