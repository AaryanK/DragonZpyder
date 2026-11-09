"""End-to-end Hatchet embedded acceptance: real worker dispatch, real PostgreSQL.

Run only on a disposable CI PostgreSQL service. A Hatchet sidecar + worker
executes the actual DragonZpyder reconciliation task twice. This is not a
mocked Hatchet task and cannot call a model or external account provider.

    cd api && DRAGONZPYDER_HATCHET_EMBEDDED_CI=1 \
      python -m agent_platform.hatchet_embedded_acceptance

The Hatchet embedded SDK downloads a verified sidecar binary on first use.
"""
from __future__ import annotations

import asyncio
import os
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import asyncpg
from cryptography.fernet import Fernet


async def prepare():
    from .goal_store import DurableGoalStore, SCHEMA
    dsn = os.environ["DRAGONZPYDER_GOALS_DATABASE_URL"]
    pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=2)
    try:
        async with pool.acquire() as con:
            await con.execute(SCHEMA)
        store = DurableGoalStore(pool, encryption_key=Fernet.generate_key().decode())
        probe = await store.register(
            source_app="internal_canary", kind="personal",
            user_id="internal-staging-probe", workspace_id=None,
            request_id=str(uuid4()),
            goal="Synthetic CI probe only: zero model or external tool calls.",
            schedule={"type": "interval", "every_seconds": 600},
        )
        user = await store.register(
            source_app="operly", kind="workspace",
            user_id="synthetic-user", workspace_id="synthetic-workspace",
            request_id=str(uuid4()), goal="Authorization required before execution",
            schedule={"type": "interval", "every_seconds": 600},
        )
        async with pool.acquire() as con:
            await con.execute(
                """UPDATE dragonzpyder_goals
                   SET next_run_at=$1 WHERE goal_id = ANY($2::uuid[])""",
                datetime.now(timezone.utc) - timedelta(seconds=5),
                [UUID(probe["goal_id"]), UUID(user["goal_id"])],
            )
        return probe["goal_id"], user["goal_id"]
    finally:
        await pool.close()


async def verify(probe_id, user_id):
    from .goal_store import DurableGoalStore
    pool = await asyncpg.create_pool(
        dsn=os.environ["DRAGONZPYDER_GOALS_DATABASE_URL"], min_size=1, max_size=2
    )
    try:
        store = DurableGoalStore(pool, encryption_key=Fernet.generate_key().decode())
        probe_runs = await store.list_runs(
            source_app="internal_canary", kind="personal",
            user_id="internal-staging-probe", workspace_id=None,
            goal_id=probe_id,
        )
        user_runs = await store.list_runs(
            source_app="operly", kind="workspace",
            user_id="synthetic-user", workspace_id="synthetic-workspace",
            goal_id=user_id,
        )
        assert len(probe_runs) == 1, probe_runs
        assert probe_runs[0]["status"] == "completed", probe_runs
        assert probe_runs[0]["attempts"] == 1, probe_runs
        assert len(probe_runs[0]["evidence_sha256"] or "") == 64
        assert len(user_runs) == 1
        assert user_runs[0]["status"] == "awaiting_authorization"
        assert user_runs[0]["attempts"] == 0
        return {"probe_run": probe_runs[0]["run_id"],
                "probe_receipt": probe_runs[0]["evidence_sha256"],
                "user_goal": "awaiting_authorization",
                "run_occurrences": len(probe_runs)}
    finally:
        await pool.close()



async def seed_autonomous_cron_probe() -> str:
    """Add a new due occurrence AFTER both direct-dispatch assertions."""
    from .goal_store import DurableGoalStore
    pool = await asyncpg.create_pool(
        dsn=os.environ["DRAGONZPYDER_GOALS_DATABASE_URL"], min_size=1, max_size=2
    )
    try:
        store = DurableGoalStore(pool, encryption_key=Fernet.generate_key().decode())
        probe = await store.register(
            source_app="internal_canary", kind="personal",
            user_id="internal-staging-probe", workspace_id=None,
            request_id=str(uuid4()), goal="Autonomous cron-only synthetic probe",
            schedule={"type": "interval", "every_seconds": 600},
        )
        async with pool.acquire() as con:
            await con.execute(
                "UPDATE dragonzpyder_goals SET next_run_at=$1 WHERE goal_id=$2",
                datetime.now(timezone.utc) - timedelta(seconds=5),
                UUID(probe["goal_id"]),
            )
        return probe["goal_id"]
    finally:
        await pool.close()


async def is_cron_probe_complete(goal_id: str) -> bool:
    from .goal_store import DurableGoalStore
    pool = await asyncpg.create_pool(
        dsn=os.environ["DRAGONZPYDER_GOALS_DATABASE_URL"], min_size=1, max_size=1
    )
    try:
        store = DurableGoalStore(pool, encryption_key=Fernet.generate_key().decode())
        rows = await store.list_runs(
            source_app="internal_canary", kind="personal",
            user_id="internal-staging-probe", workspace_id=None, goal_id=goal_id,
        )
        return (len(rows) == 1 and rows[0]["status"] == "completed"
                and rows[0]["attempts"] == 1
                and len(rows[0]["evidence_sha256"] or "") == 64)
    finally:
        await pool.close()


def main():
    if (os.getenv("DRAGONZPYDER_HATCHET_EMBEDDED_CI") != "1"
            or os.getenv("DRAGONZPYDER_STAGE") != "staging"
            or "localhost" not in os.getenv("DRAGONZPYDER_GOALS_DATABASE_URL", "")):
        raise RuntimeError("Embedded acceptance requires isolated CI database")
    from hatchet_sdk import Hatchet
    from .goal_tick import GoalTickInput, make_goal_tick_task, require_synthetic_gate
    require_synthetic_gate()
    probe_id, user_id = asyncio.run(prepare())
    hatchet = Hatchet.from_embedded()
    task = make_goal_tick_task(hatchet)
    worker = hatchet.worker("dragonzpyder-embedded-goal-smoke", slots=1,
                            workflows=[task])
    try:
        threading.Thread(target=worker.start, daemon=True).start()
        time.sleep(3)
        first = task.run(GoalTickInput())
        assert first["scheduled"] == {"pending": 1, "awaiting_authorization": 1}, first
        assert len(first["probes"]) == 1, first
        assert first["probes"][0]["status"] == "completed", first
        assert first["model_calls"] == 0 and first["personal_tool_calls"] == 0
        # Distinct real Hatchet dispatch must not replay the same occurrence.
        second = task.run(GoalTickInput())
        assert second["scheduled"] == {"pending": 0, "awaiting_authorization": 0}
        assert second["probes"] == []
        verified = asyncio.run(verify(probe_id, user_id))
        print("HATCHET_EMBEDDED_ACCEPTANCE_PASS", verified, flush=True)

        # A truly scheduled run must happen without task.run() or any other
        # direct trigger. The source of dispatch is Hatchet's persistent cron.
        # Use a separate new due goal so the previous idempotency test remains
        # independently verified.
        cron_probe_id = asyncio.run(seed_autonomous_cron_probe())
        asyncio.run(task.aio_create_cron(
            cron_name="dragonzpyder-embedded-cron-acceptance-v1",
            expression="* * * * *",
            input=GoalTickInput(),
        ))
        deadline = time.monotonic() + 100
        confirmed = False
        while time.monotonic() < deadline:
            confirmed = asyncio.run(is_cron_probe_complete(cron_probe_id))
            if confirmed:
                break
            time.sleep(2)
        assert confirmed, "Hatchet cron did not autonomously dispatch a due goal"
        print("HATCHET_EMBEDDED_CRON_ACCEPTANCE_PASS",
              {"goal_id": cron_probe_id, "model_calls": 0,
               "external_tool_calls": 0}, flush=True)
    finally:
        hatchet.stop_embedded()
    # Embedded worker child processes can outlive this standalone test runner.
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
