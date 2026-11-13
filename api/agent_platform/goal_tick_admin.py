"""Explicit STAGING operator commands for persistent autonomous smoke.

Usage (on an isolated DragonZpyder staging worker with proper secrets):
  python -m agent_platform.goal_tick_admin install-cron
  python -m agent_platform.goal_tick_admin seed-probe

The first registers a durable Hatchet minute cron; the second registers a
synthetic recurring DB-only goal. Neither command touches personal accounts,
runs a model, or invokes an MCP. Both are fail-closed without staging flags.
"""
from __future__ import annotations

import asyncio
import os
import sys
from uuid import NAMESPACE_DNS, uuid5


def _operator_guard(mode: str):
    from .goal_tick import require_synthetic_gate
    require_synthetic_gate()
    if os.getenv("DRAGONZPYDER_STAGE") != "staging":
        raise RuntimeError("Persistent synthetic-goal operations are staging-only")
    if os.getenv("DRAGONZPYDER_GOAL_CRON_INSTALL_ALLOWED") != "1":
        raise RuntimeError("Operator has not approved staged goal automation")
    if mode not in ("install-cron", "seed-probe"):
        raise ValueError("Expected install-cron or seed-probe")


async def run(mode: str) -> dict:
    _operator_guard(mode)
    if mode == "install-cron":
        from hatchet_sdk import Hatchet
        from .goal_tick import make_goal_tick_task, install_staging_goal_cron
        hatchet = Hatchet()
        cron = await install_staging_goal_cron(make_goal_tick_task(hatchet))
        return {"action": "install-cron", "operator": "staging",
                "cron_name": "dragonzpyder-staging-goal-reconcile-v1",
                "registration_response_type": type(cron).__name__}

    import asyncpg
    from .goal_store import DurableGoalStore
    pool = await asyncpg.create_pool(
        dsn=os.environ["DRAGONZPYDER_GOALS_DATABASE_URL"], min_size=1, max_size=2,
    )
    try:
        async with pool.acquire() as con:
            if await con.fetchval("SELECT to_regclass('dragonzpyder_goal_runs')") is None:
                raise RuntimeError("Durable goal occurrence schema not installed")
        store = DurableGoalStore(
            pool, encryption_key=os.environ["DRAGONZPYDER_GOALS_ENCRYPTION_KEY"],
        )
        row = await store.register(
            source_app="internal_canary", kind="personal",
            user_id="internal-staging-probe", workspace_id=None,
            request_id=str(uuid5(NAMESPACE_DNS, "dragonzpyder:staging:goal-tick:v1")),
            goal="DB-only synthetic recurring scheduler proof. No model or tools.",
            schedule={"type": "interval", "every_seconds": 60},
        )
        return {"action": "seed-probe", "goal_id": row["goal_id"],
                "next_run_at": row["next_run_at"],
                "synthetic_only": True, "real_user_goal": False}
    finally:
        await pool.close()


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m agent_platform.goal_tick_admin install-cron|seed-probe")
    result = asyncio.run(run(sys.argv[1]))
    print(result)


if __name__ == "__main__":
    main()
