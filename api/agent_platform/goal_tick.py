"""Hatchet-owned durable minute wakeup for DragonZpyder goals.

An operator provisions ONE named cron with install_staging_goal_cron().
The task contains no user data or credentials. Each tick independently
reconciles due occurrences from PostgreSQL, allowing recovery after outages.
The first live mode is deliberately synthetic DB-only; it cannot spend money
or call an MCP, Operly provider, browser, or local computer.
"""
from __future__ import annotations

import os
from datetime import timedelta
from typing import Literal

from pydantic import BaseModel, Field


class GoalTickInput(BaseModel):
    mode: Literal["reconcile"] = "reconcile"


def require_synthetic_gate() -> None:
    conditions = (
        "DRAGONZPYDER_GOAL_STORE_ENABLED",
        "DRAGONZPYDER_GOAL_TICK_ENABLED",
        "DRAGONZPYDER_GOAL_SYNTHETIC_ONLY",
    )
    if not all(os.getenv(name) == "1" for name in conditions):
        raise RuntimeError("Goal tick is disabled or not restricted to synthetic tasks")
    dsn = os.getenv("DRAGONZPYDER_GOALS_DATABASE_URL", "")
    if not dsn.startswith(("postgres://", "postgresql://")):
        raise RuntimeError("Persistent Postgres goal store is required")


async def execute_goal_tick() -> dict:
    """Invoke actual Postgres ledger logic. Never execute user goals."""
    require_synthetic_gate()
    import asyncpg
    from .goal_reconciler import GoalReconciler
    from .goal_reconciler_schema import RUN_SCHEMA

    pool = await asyncpg.create_pool(
        dsn=os.environ["DRAGONZPYDER_GOALS_DATABASE_URL"], min_size=1, max_size=2,
    )
    try:
        async with pool.acquire() as con:
            if (await con.fetchval(
                "SELECT to_regclass('dragonzpyder_goal_runs')"
            )) is None:
                raise RuntimeError("Goal runs migration missing; fail closed")
        result = await GoalReconciler(pool).tick()
        if os.getenv("DRAGONZPYDER_WEB_EVENT_ENABLED") == "1":
            from .web_event_watch import require_web_event_gate, run_due_web_checks
            require_web_event_gate()
            async with pool.acquire() as con:
                for table in ("dragonzpyder_event_watches",
                              "dragonzpyder_event_inbox", "dragonzpyder_event_wakes"):
                    if await con.fetchval("SELECT to_regclass($1)", table) is None:
                        raise RuntimeError("Event monitoring migration missing")
            result["events"] = await run_due_web_checks(pool)
        return result
    finally:
        await pool.close()


def make_goal_tick_task(hatchet):
    """Install a named Hatchet task, but NEVER install a cron automatically."""
    @hatchet.task(
        name="dragonzpyder-goal-reconcile-v1",
        input_validator=GoalTickInput,
        concurrency=1,
        retries=1,
        execution_timeout=timedelta(seconds=45),
    )
    async def run(input: GoalTickInput, ctx) -> dict:
        if input.mode != "reconcile":
            raise ValueError("Invalid tick payload")
        return await execute_goal_tick()

    return run


async def install_staging_goal_cron(tick_task):
    """Operator-only, explicit registration into persistent Hatchet control plane."""
    require_synthetic_gate()
    if (os.getenv("DRAGONZPYDER_GOAL_CRON_INSTALL_ALLOWED") != "1"
            or os.getenv("DRAGONZPYDER_STAGE") != "staging"):
        raise RuntimeError("Only approved staging operator can provision cron")
    # Cron is managed by Hatchet, not a Python polling loop. Never run this
    # from routine worker startup: repeated deployment must not create duplicates.
    return await tick_task.aio_create_cron(
        cron_name="dragonzpyder-staging-goal-reconcile-v1",
        expression="* * * * *",
        input=GoalTickInput(),
    )
