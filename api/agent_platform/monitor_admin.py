"""Explicit operator-only Hatchet cron registration for staging web monitors.

Example (INSIDE staging worker, with approved environment):
    python -m agent_platform.monitor_admin create \
       --monitor-id physics-news --query 'DUNE neutrino detector news' \
       --provider wikipedia --cron '0 9 * * *'

No cron is installed at worker boot, GitHub push, or CI execution.
User-facing monitor creation requires future verified identity and authorization.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import re

from .monitor import MonitorInput, make_monitor_task

HOURLY = re.compile(r"^(?:[0-5]?\d) \* \* \* \*$")
HOURLY_INTERVAL = re.compile(r"^([0-5]?\d) \*/(\d{1,2}) \* \* \*$")
DAILY = re.compile(r"^([0-5]?\d) ([01]?\d|2[0-3]) \* \* \*$")
WEEKLY = re.compile(r"^([0-5]?\d) ([01]?\d|2[0-3]) \* \* ([0-6])$")


def validate_cron(expression: str) -> str:
    if not isinstance(expression, str):
        raise ValueError("Cron expression must be text")
    expression = " ".join(expression.split())
    if HOURLY.fullmatch(expression) or DAILY.fullmatch(expression) or WEEKLY.fullmatch(expression):
        return expression
    interval = HOURLY_INTERVAL.fullmatch(expression)
    if interval and 2 <= int(interval.group(2)) <= 23:
        return expression
    raise ValueError("Monitor cron may run at most hourly")


def authorized() -> bool:
    return all(os.getenv(k) == "1" for k in (
        "DRAGONZPYDER_MONITOR_ADMIN_ENABLED",
        "DRAGONZPYDER_WEB_MONITOR_ENABLED",
        "DRAGONZPYDER_AGENT_WEB_SEARCH_ENABLED",
        "DRAGONZPYDER_AGENT_HARNESS_V2",
        "DRAGONZPYDER_AGENT_WORKER_ALLOWED",
    ))


async def register(*, monitor_id: str, query: str, expression: str,
                   provider: str = "wikipedia", max_results: int = 3):
    if not authorized():
        raise RuntimeError("Operator cron creation is disabled")
    from hatchet_sdk import Hatchet
    requested = MonitorInput(
        monitor_id=monitor_id, query=query, provider=provider,
        max_results=max_results,
    )
    cron = validate_cron(expression)
    task = make_monitor_task(Hatchet())
    created = await task.aio_create_cron(
        cron_name="dragonzpyder-staging-monitor-" + requested.monitor_id,
        expression=cron,
        input=requested,
    )
    return {"monitor_id": requested.monitor_id, "expression": cron,
            "created": bool(created)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["create"])
    parser.add_argument("--monitor-id", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--provider", choices=["wikipedia", "brave", "searxng"], default="wikipedia")
    parser.add_argument("--cron", required=True)
    parser.add_argument("--max-results", type=int, default=3)
    args = parser.parse_args()
    result = asyncio.run(register(
        monitor_id=args.monitor_id, query=args.query,
        expression=args.cron, provider=args.provider,
        max_results=args.max_results,
    ))
    # No secrets, model context, or provider raw responses here.
    print(result)


if __name__ == "__main__":
    main()
