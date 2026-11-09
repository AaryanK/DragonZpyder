"""Real Postgres goal persistence, idempotency, tenant isolation and encryption.

Runs only on a disposable CI database; no user data, inference or scheduled
agent execution. Uses a fresh schema and drops it after every test.
"""
import asyncio
import os
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_platform.goal_store import DurableGoalStore, GoalConflict, SCHEMA


@pytest.mark.skipif(not os.getenv("DRAGONZPYDER_BUDGET_TEST_DSN"),
                    reason="Requires isolated test PostgreSQL")
def test_registered_goal_persists_across_restart_but_never_executes():
    import asyncpg

    async def scenario():
        dsn = os.environ["DRAGONZPYDER_BUDGET_TEST_DSN"]
        schema = "dz_goals_test_" + uuid4().hex
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
            key = Fernet.generate_key().decode()
            store = DurableGoalStore(pool, encryption_key=key)
            request_id = str(uuid4())
            attributes = dict(
                source_app="operly", kind="workspace",
                user_id="test-user", workspace_id="workspace-a",
                request_id=request_id,
                goal="PRIVATE goal text - MUST BE ENCRYPTED",
                schedule={"type": "cron", "timezone": "UTC", "expression": "0 9 * * 1"},
            )
            result = await store.register(**attributes)
            assert result["status"] == "registered"
            assert result["execution_started"] is False
            assert result["job_registered"] is False
            assert result["requires_fresh_authorization"] is True
            assert result["next_run_at"] is not None
            async with pool.acquire() as con:
                stored = await con.fetchrow(
                    "SELECT goal_ciphertext,principal_hash,payload_sha256 FROM dragonzpyder_goals"
                )
            assert b"PRIVATE goal text" not in bytes(stored["goal_ciphertext"])
            assert b"PRIVATE goal text" not in str(stored).encode()
            assert stored["principal_hash"] != "test-user"
            restarted = DurableGoalStore(pool, encryption_key=key)
            same = await restarted.register(**attributes)
            assert same["goal_id"] == result["goal_id"]
            with pytest.raises(GoalConflict):
                await restarted.register(**{**attributes, "goal": "another goal"})
            with pytest.raises(LookupError):
                await restarted.get(
                    source_app="operly", kind="workspace",
                    user_id="another-user", workspace_id="workspace-a",
                    goal_id=result["goal_id"],
                )
            with pytest.raises(LookupError):
                await restarted.get(
                    source_app="operly", kind="workspace",
                    user_id="test-user", workspace_id="workspace-b",
                    goal_id=result["goal_id"],
                )
            cancelled = await restarted.cancel(
                source_app="operly", kind="workspace",
                user_id="test-user", workspace_id="workspace-a",
                goal_id=result["goal_id"],
            )
            assert cancelled["status"] == "cancelled"
            assert cancelled["next_run_at"] is None
            replay = await restarted.register(**attributes)
            assert replay["status"] == "cancelled"
        finally:
            if pool:
                await pool.close()
            try:
                await admin.execute('DROP SCHEMA IF EXISTS "' + schema + '" CASCADE')
            finally:
                await admin.close()

    asyncio.run(scenario())



def test_principal_hash_cannot_be_confused_by_user_delimiters():
    from agent_platform.goal_store import _principal
    first = _principal(
        source_app="operly", kind="workspace",
        user_id="abc\\0x", workspace_id="y",
    )
    second = _principal(
        source_app="operly", kind="workspace",
        user_id="abc", workspace_id="x\\0y",
    )
    assert first != second
    internal = _principal(
        source_app="internal_canary", kind="personal",
        user_id="internal-staging-probe", workspace_id=None,
    )
    user = _principal(
        source_app="dragonzpyder", kind="personal",
        user_id="internal-staging-probe", workspace_id=None,
    )
    assert internal != user
