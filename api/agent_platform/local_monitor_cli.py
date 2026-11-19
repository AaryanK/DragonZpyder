"""Staging operator CLI; snapshot requires no DB or paid model.

python -m agent_platform.local_monitor_cli snapshot
python -m agent_platform.local_monitor_cli migrate
python -m agent_platform.local_monitor_cli once
python -m agent_platform.local_monitor_cli history
python -m agent_platform.local_monitor_cli install-cron
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os

from .local_monitor import (
    MONITOR_SCHEMA, execute_local_monitor_tick, install_staging_monitor_cron,
    make_local_monitor_task, require_monitor_gate,
)


async def _migrate() -> dict:
    require_monitor_gate()
    if os.getenv("DRAGONZPYDER_LOCAL_MONITOR_SCHEMA_INSTALL_ALLOWED") != "1":
        raise RuntimeError("Explicit staging schema approval required")
    import asyncpg
    con = await asyncpg.connect(os.environ["DRAGONZPYDER_LOCAL_MONITOR_DATABASE_URL"])
    try:
        async with con.transaction():
            await con.execute(MONITOR_SCHEMA)
        return {"schema_ready": True}
    finally:
        await con.close()


async def _history() -> dict:
    require_monitor_gate()
    import asyncpg
    con = await asyncpg.connect(os.environ["DRAGONZPYDER_LOCAL_MONITOR_DATABASE_URL"])
    try:
        rows = await con.fetch(
            """SELECT observed_at, observation, decision, receipt_sha256
               FROM dragonzpyder_local_observations
               WHERE monitor_key='worker-health'
               ORDER BY bucket_start DESC LIMIT 20"""
        )
        return {"monitor_key": "worker-health", "observations": [
            {"observed_at": row["observed_at"].isoformat(),
             "observation": json.loads(row["observation"]) if isinstance(row["observation"], str) else row["observation"],
             "decision": json.loads(row["decision"]) if isinstance(row["decision"], str) else row["decision"],
             "receipt_sha256": row["receipt_sha256"]}
            for row in rows
        ]}
    finally:
        await con.close()


async def _install_cron() -> dict:
    require_monitor_gate()
    if os.getenv("DRAGONZPYDER_LOCAL_MONITOR_CRON_INSTALL_ALLOWED") != "1":
        raise RuntimeError("Operator approval required before registering a cron")
    from hatchet_sdk import Hatchet
    hatchet = Hatchet()
    await install_staging_monitor_cron(make_local_monitor_task(hatchet))
    return {"cron_submitted": True, "cron_name": "dragonzpyder-staging-worker-health-v1"}


def main() -> None:
    parser = argparse.ArgumentParser(description="DragonZpyder local worker monitor")
    parser.add_argument("command", choices=("snapshot", "migrate", "once", "history", "install-cron"))
    cmd = parser.parse_args().command
    if cmd == "snapshot":
        from .local_monitor import sample_local_tools
        output = sample_local_tools()
    elif cmd == "migrate":
        output = asyncio.run(_migrate())
    elif cmd == "once":
        output = asyncio.run(execute_local_monitor_tick())
    elif cmd == "history":
        output = asyncio.run(_history())
    else:
        output = asyncio.run(_install_cron())
    print(json.dumps(output, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
