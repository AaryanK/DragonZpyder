"""Operator-only, explicit PostgreSQL schema deployment for isolated staging.

Importing this module performs no migrations. An operator must first verify
that the DSN is a disposable DragonZpyder *staging* database with its own
backups and then set the explicit approval flag.
"""
from __future__ import annotations

import asyncio
import os


async def migrate() -> dict:
    if (os.getenv("RAILWAY_ENVIRONMENT_NAME") != "staging"
            or os.getenv("DRAGONZPYDER_STAGE") != "staging"
            or os.getenv("DRAGONZPYDER_APPLY_STAGING_TASK_SCHEMA") != "1"):
        raise RuntimeError("Staging task schema operation requires explicit operator approval")
    dsn = os.getenv("DRAGONZPYDER_GOALS_DATABASE_URL", "")
    if not dsn.startswith(("postgres://", "postgresql://")):
        raise RuntimeError("Dedicated staging goals database is not configured")
    import asyncpg
    from .goal_store import SCHEMA
    con = await asyncpg.connect(dsn=dsn, timeout=8, command_timeout=20)
    try:
        async with con.transaction():
            await con.execute(SCHEMA)
            tables = [
                "dragonzpyder_goals", "dragonzpyder_goal_runs",
                "dragonzpyder_ui_tasks", "dragonzpyder_ui_task_events",
                "dragonzpyder_event_inbox", "dragonzpyder_event_wakes",
            ]
            for table in tables:
                if await con.fetchval("SELECT to_regclass($1)", table) is None:
                    raise RuntimeError("Staging schema verification failed")
        return {"status": "schema_ready", "table_count_checked": len(tables)}
    finally:
        await con.close()


if __name__ == "__main__":
    print(asyncio.run(migrate()), flush=True)
