"""Real PostgreSQL isolation and sanitized activity for web harness tasks."""
import asyncio
import os
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet

from agent_platform.task_activity import ActivityStore, TASK_SCHEMA


@pytest.mark.skipif(not os.getenv("DRAGONZPYDER_BUDGET_TEST_DSN"),
                    reason="Requires disposable CI PostgreSQL")
def test_activity_owner_isolation_encryption_cancel_and_stale_result():
    import asyncpg

    async def scenario():
        dsn = os.environ["DRAGONZPYDER_BUDGET_TEST_DSN"]
        schema = "dz_activity_" + uuid4().hex
        connection = await asyncpg.connect(dsn)
        pool = None
        try:
            await connection.execute('CREATE SCHEMA "' + schema + '"')
            pool = await asyncpg.create_pool(
                dsn, min_size=1, max_size=3, server_settings={"search_path": schema},
            )
            async with pool.acquire() as con:
                await con.execute(TASK_SCHEMA)
            store = ActivityStore(pool, encryption_key=Fernet.generate_key().decode())
            request_id = str(uuid4())
            task, created = await store.create(
                owner="user-one@example.test", request_id=request_id,
                kind="probe", prompt="PRIVATE task and SECRET context",
            )
            assert created
            again, new = await store.create(
                owner="user-one@example.test", request_id=request_id,
                kind="probe", prompt="PRIVATE task and SECRET context",
            )
            assert not new and again["task_id"] == task["task_id"]
            with pytest.raises(ValueError):
                await store.create(
                    owner="user-one@example.test", request_id=request_id,
                    kind="agent", prompt="Different request",
                )

            async with pool.acquire() as con:
                record = await con.fetchrow(
                    "SELECT prompt_ciphertext FROM dragonzpyder_ui_tasks WHERE task_id=$1",
                    __import__("uuid").UUID(task["task_id"]),
                )
            assert b"PRIVATE task" not in bytes(record["prompt_ciphertext"])
            assert await store.list(owner="user-two@example.test") == []
            with pytest.raises(LookupError):
                await store.get(
                    owner="user-two@example.test", task_id=task["task_id"]
                )
            claim = await store.claim(task["task_id"])
            assert claim
            row, token = claim
            assert row["status"] == "running"
            assert await store.claim(task["task_id"]) is None
            await store.append(task["task_id"], "started", "Worker accepted the task")
            assert await store.finish(
                task_id=task["task_id"], claim_token=token,
                status="completed", answer="Only the owner may read this",
            )
            detail = await store.get(
                owner="user-one@example.test", task_id=task["task_id"],
            )
            assert detail["status"] == "completed"
            assert detail["answer"] == "Only the owner may read this"
            assert any(e["kind"] == "started" for e in detail["events"])
            administrator = await store.get(owner=None, task_id=task["task_id"], admin=True)
            assert "answer" not in administrator
            assert "PRIVATE task" not in str(administrator)
            assert "Only the owner" not in str(administrator)

            task2, _ = await store.create(
                owner="user-one@example.test", request_id=str(uuid4()),
                kind="probe", prompt="Cancel my pending task",
            )
            owner_cancel = await store.cancel(
                owner="user-one@example.test", task_id=task2["task_id"],
            )
            assert owner_cancel["status"] == "cancelled"
            assert await store.claim(task2["task_id"]) is None

            task3, _ = await store.create(
                owner="user-one@example.test", request_id=str(uuid4()),
                kind="probe", prompt="Cancel while running",
            )
            _, claim_token = await store.claim(task3["task_id"])
            await store.cancel(owner="user-one@example.test", task_id=task3["task_id"])
            assert not await store.finish(
                task_id=task3["task_id"], claim_token=claim_token,
                status="completed", answer="MUST NOT COMMIT",
            )
            canceled = await store.get(
                owner="user-one@example.test", task_id=task3["task_id"],
            )
            assert canceled["status"] == "cancelled"
            assert not canceled.get("answer")
        finally:
            if pool:
                await pool.close()
            try:
                await connection.execute('DROP SCHEMA IF EXISTS "' + schema + '" CASCADE')
            finally:
                await connection.close()

    asyncio.run(scenario())
