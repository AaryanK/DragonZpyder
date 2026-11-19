"""Provision one operator-owned web-event watch and one waiting canary.

Only staging. The existing Hatchet goal-reconcile minute cron polls due web
checks at the configured interval, then delivers the event to the durable
wait journal. No additional homegrown scheduler or user account token.
"""
from __future__ import annotations

import asyncio
import os
import sys
from uuid import NAMESPACE_DNS, uuid5


async def arm_web_event() -> dict:
    from .web_event_watch import require_web_event_gate, register_operator_watch
    from .event_wait import EventWaitStore
    import asyncpg

    require_web_event_gate()
    if os.getenv("DRAGONZPYDER_GOAL_CRON_INSTALL_ALLOWED") != "1":
        raise RuntimeError("Staging operator approval is required")
    monitor_id = os.getenv("DRAGONZPYDER_WEB_EVENT_MONITOR_ID", "")
    query = os.getenv("DRAGONZPYDER_WEB_EVENT_QUERY", "")
    interval = int(os.getenv("DRAGONZPYDER_WEB_EVENT_INTERVAL_SECONDS", "600"))
    dsn = os.getenv("DRAGONZPYDER_GOALS_DATABASE_URL", "")
    if not dsn.startswith(("postgres://", "postgresql://")):
        raise RuntimeError("DragonZpyder goals database is missing")

    pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=2)
    try:
        async with pool.acquire() as con:
            for table in ("dragonzpyder_event_watches",
                          "dragonzpyder_event_waits", "dragonzpyder_event_wakes"):
                if await con.fetchval("SELECT to_regclass($1)", table) is None:
                    raise RuntimeError("Durable event migration is missing")
        watch = await register_operator_watch(
            pool, monitor_id=monitor_id, query=query,
            interval_seconds=interval,
        )
        wait = await EventWaitStore(pool).subscribe(
            source_app="internal_canary", kind="personal",
            user_id="internal-staging-probe", workspace_id=None,
            monitor_id=monitor_id,
            request_id=str(uuid5(NAMESPACE_DNS, "dz:web-event-wait:v1:" + monitor_id)),
        )
        return {"watch": watch, "wait": wait,
                "hatchet_cron": "dragonzpyder-staging-goal-reconcile-v1",
                "provider": "wikipedia", "synthetic_only": True,
                "objective_verified": False}
    finally:
        await pool.close()


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] != "arm-watch":
        raise SystemExit("Usage: python -m agent_platform.web_event_admin arm-watch")
    result = asyncio.run(arm_web_event())
    # Never print query text: operational logs may be accessible to others.
    print(result, flush=True)


if __name__ == "__main__":
    main()
