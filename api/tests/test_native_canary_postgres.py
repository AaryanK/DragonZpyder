"""Two real Postgres native math wakes, idempotency and ownership, no MCP."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch
from uuid import uuid4

import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_platform.native_canary import (
    SCHEMA, NativeCanaryWake, execute_native_canary_wake, native_canary_tools,
)


def test_two_wakes_durable_receipts_replay_and_owner_fence():
    dsn = os.environ["DRAGONZPYDER_BUDGET_TEST_DSN"]
    goal_id, user_id, conversation_id, other_user = (
        str(uuid4()) for _ in range(4)
    )

    async def run():
        con = await asyncpg.connect(dsn)
        try:
            await con.execute(SCHEMA)
            await con.execute(
                """INSERT INTO dz_native_canary_goals
                   (goal_id,user_id,conversation_id,state)
                   VALUES($1,$2,$3,'active')""",
                goal_id,user_id,conversation_id,
            )
        finally:
            await con.close()
        try:
            first = await execute_native_canary_wake(
                NativeCanaryWake(goal_id=goal_id, sequence=0)
            )
            assert first["state"] == "active"
            assert first["next_sequence"] == 1
            assert first["tool"] == "check_quadratic_gradient_step"

            repeated = await execute_native_canary_wake(
                NativeCanaryWake(goal_id=goal_id, sequence=0)
            )
            assert repeated["executed"] is False
            assert repeated["state"] == "already_processed"

            second = await execute_native_canary_wake(
                NativeCanaryWake(goal_id=goal_id, sequence=1)
            )
            assert second["state"] == "completed"
            assert second["next_sequence"] == 2

            no_replay = await execute_native_canary_wake(
                NativeCanaryWake(goal_id=goal_id, sequence=1)
            )
            assert no_replay["executed"] is False

            signed = native_canary_tools(
                user_id=user_id,conversation_id=conversation_id,
            )
            status = await signed[1].ainvoke({"goal_id": goal_id})
            assert status["state"] == "completed"
            assert status["verified"] is True
            assert status["completed_wakes"] == 2
            assert [x["sequence"] for x in status["receipts"]] == [0,1]
            assert all(x["tool"] == "check_quadratic_gradient_step"
                       for x in status["receipts"])
            assert all(x["output"]["arithmetic_valid"] is True
                       for x in status["receipts"])
            for item in status["receipts"]:
                content = json.dumps(item["output"], sort_keys=True)
                assert item["result_sha256"] == hashlib.sha256(
                    content.encode("utf-8")
                ).hexdigest()
            # A separate identity must never be able to inspect this goal.
            outsider = native_canary_tools(
                user_id=other_user,conversation_id=conversation_id,
            )
            missing = await outsider[1].ainvoke({"goal_id": goal_id})
            assert missing["status"] == "not_found"
            cannot_cancel = await outsider[2].ainvoke({"goal_id": goal_id})
            assert cannot_cancel["status"] == "not_cancellable"
        finally:
            con = await asyncpg.connect(dsn)
            try:
                await con.execute(
                    "DELETE FROM dz_native_canary_receipts WHERE goal_id=$1",
                    goal_id,
                )
                await con.execute(
                    "DELETE FROM dz_native_canary_goals WHERE goal_id=$1",
                    goal_id,
                )
            finally:
                await con.close()

    with patch.dict(os.environ, {
        "DRAGONZPYDER_NATIVE_CANARY_ENABLED": "1",
        "DRAGONZPYDER_PERSONAL_MCP_DATABASE_URL": dsn,
    }, clear=False):
        asyncio.run(run())


def test_out_of_order_wake_fails_closed_without_math_execution():
    dsn = os.environ["DRAGONZPYDER_BUDGET_TEST_DSN"]
    goal_id, user_id, conversation_id = (str(uuid4()) for _ in range(3))

    async def run():
        con = await asyncpg.connect(dsn)
        try:
            await con.execute(SCHEMA)
            await con.execute(
                """INSERT INTO dz_native_canary_goals
                   (goal_id,user_id,conversation_id,state)
                   VALUES($1,$2,$3,'active')""",
                goal_id,user_id,conversation_id,
            )
        finally:
            await con.close()
        try:
            wrong = await execute_native_canary_wake(
                NativeCanaryWake(goal_id=goal_id,sequence=1)
            )
            assert wrong == {
                "state":"blocked","reason":"out_of_order","executed":False
            }
            own = native_canary_tools(
                user_id=user_id, conversation_id=conversation_id,
            )
            status = await own[1].ainvoke({"goal_id":goal_id})
            assert status["state"] == "blocked"
            assert status["blocked_reason"] == "out_of_order"
            assert status["completed_wakes"] == 0
        finally:
            con = await asyncpg.connect(dsn)
            try:
                await con.execute(
                    "DELETE FROM dz_native_canary_receipts WHERE goal_id=$1",
                    goal_id,
                )
                await con.execute(
                    "DELETE FROM dz_native_canary_goals WHERE goal_id=$1",
                    goal_id,
                )
            finally:
                await con.close()

    with patch.dict(os.environ, {
        "DRAGONZPYDER_NATIVE_CANARY_ENABLED": "1",
        "DRAGONZPYDER_PERSONAL_MCP_DATABASE_URL": dsn,
    }, clear=False):
        asyncio.run(run())
