"""Durable recurring worker-health agent, executed by Hatchet.

Hatchet handles wakes; PostgreSQL owns state, deduplication and history.
Each wake calls a small set of local tools once and decides whether to alert.
No model inference, shell, external MCP, or user-account access occurs.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from pydantic import BaseModel

from .local_tools import LocalToolRegistry

MONITOR_SCHEMA = """
CREATE TABLE IF NOT EXISTS dragonzpyder_local_observations (
    monitor_key text NOT NULL,
    bucket_start timestamptz NOT NULL,
    observed_at timestamptz NOT NULL,
    observation jsonb NOT NULL,
    decision jsonb NOT NULL,
    receipt_sha256 char(64) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (monitor_key, bucket_start)
);
CREATE INDEX IF NOT EXISTS dz_local_observations_recent
    ON dragonzpyder_local_observations (monitor_key, observed_at DESC);
"""
VALID_INTERVALS = frozenset({1, 5, 10, 15, 30, 60})
_MONITOR_KEY = re.compile(r"^[a-z][a-z0-9_-]{2,49}$")


class LocalMonitorInput(BaseModel):
    monitor_key: Literal["worker-health"] = "worker-health"


@dataclass(frozen=True)
class MonitorPolicy:
    interval_minutes: int = 5
    memory_warn_percent: float = 85.0
    disk_warn_percent: float = 90.0
    memory_jump_points: float = 15.0

    def __post_init__(self) -> None:
        if type(self.interval_minutes) is not int or self.interval_minutes not in VALID_INTERVALS:
            raise ValueError("Monitoring interval must divide an hour")
        for threshold in (self.memory_warn_percent, self.disk_warn_percent):
            if not isinstance(threshold, (int, float)) or not 50 <= threshold <= 99:
                raise ValueError("Utilization alert threshold must be 50–99%")
        if not isinstance(self.memory_jump_points, (int, float)) or not 1 <= self.memory_jump_points <= 50:
            raise ValueError("Memory jump threshold must be 1–50 points")


def require_monitor_gate() -> None:
    if (os.getenv("DRAGONZPYDER_LOCAL_MONITOR_ENABLED") != "1"
            or os.getenv("DRAGONZPYDER_STAGE") != "staging"):
        raise RuntimeError("Local computer monitoring is disabled outside approved staging")
    dsn = os.getenv("DRAGONZPYDER_LOCAL_MONITOR_DATABASE_URL", "")
    if not dsn.startswith(("postgres://", "postgresql://")):
        raise RuntimeError("Durable PostgreSQL is required for monitoring")


def policy_from_environment() -> MonitorPolicy:
    return MonitorPolicy(
        interval_minutes=int(os.getenv("DRAGONZPYDER_LOCAL_MONITOR_INTERVAL_MINUTES", "5")),
        memory_warn_percent=float(os.getenv("DRAGONZPYDER_LOCAL_MONITOR_MEMORY_WARN_PERCENT", "85")),
        disk_warn_percent=float(os.getenv("DRAGONZPYDER_LOCAL_MONITOR_DISK_WARN_PERCENT", "90")),
    )


def _bucket(now: datetime, minutes: int) -> datetime:
    if now.tzinfo is None:
        raise ValueError("A timezone-aware clock is required")
    seconds = 60 * minutes
    return datetime.fromtimestamp(int(now.timestamp()) // seconds * seconds, tz=timezone.utc)


def _percentage(value: dict[str, Any]) -> float:
    percentage = value.get("used_percent")
    if type(percentage) not in (int, float) or not 0 <= percentage <= 100:
        raise ValueError("Invalid local tool utilization receipt")
    return float(percentage)


def sample_local_tools(registry: LocalToolRegistry | None = None) -> dict[str, Any]:
    tools = registry if registry is not None else LocalToolRegistry()
    return {
        "time": tools.invoke("time.now", {}),
        "memory": tools.invoke("system.memory", {}),
        "disk": tools.invoke("system.disk", {}),
    }


def decide(observation: dict[str, Any], policy: MonitorPolicy, previous: dict | None) -> dict:
    memory = _percentage(observation["memory"])
    disk = _percentage(observation["disk"])
    alerts: list[str] = []
    if memory >= policy.memory_warn_percent:
        alerts.append("ram_high")
    if disk >= policy.disk_warn_percent:
        alerts.append("disk_high")
    if previous is not None:
        old = _percentage(previous["memory"])
        if memory - old >= policy.memory_jump_points:
            alerts.append("ram_jump")
    return {"status": "attention" if alerts else "healthy", "alerts": alerts}


class LocalMonitorAgent:
    """Stateful monitor: its memory is PostgreSQL, not a long-lived process."""

    def __init__(self, pool, *, registry: LocalToolRegistry | None = None,
                 policy: MonitorPolicy | None = None):
        self.pool = pool
        self.registry = registry or LocalToolRegistry()
        self.policy = policy or MonitorPolicy()

    async def tick(self, *, monitor_key: str = "worker-health",
                   now: datetime | None = None) -> dict[str, Any]:
        if not _MONITOR_KEY.fullmatch(monitor_key):
            raise ValueError("Invalid monitor key")
        when = now or datetime.now(timezone.utc)
        bucket = _bucket(when, self.policy.interval_minutes)
        async with self.pool.acquire() as con:
            row = await con.fetchrow(
                """SELECT observation, decision, receipt_sha256 FROM
                   dragonzpyder_local_observations
                   WHERE monitor_key=$1 AND bucket_start=$2""",
                monitor_key, bucket,
            )
        if row is not None:
            return _format(monitor_key, bucket, row, inserted=False)

        observation = sample_local_tools(self.registry)
        async with self.pool.acquire() as con:
            async with con.transaction():
                # One transaction-scoped lock per fixed monitor identity.
                # No lock persists if a worker crashes.
                await con.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended($1, 0))",
                    monitor_key,
                )
                existing = await con.fetchrow(
                    """SELECT observation, decision, receipt_sha256
                       FROM dragonzpyder_local_observations
                       WHERE monitor_key=$1 AND bucket_start=$2""",
                    monitor_key, bucket,
                )
                if existing is not None:
                    return _format(monitor_key, bucket, existing, inserted=False)
                older = await con.fetchrow(
                    """SELECT bucket_start, observation, decision, receipt_sha256
                       FROM dragonzpyder_local_observations
                       WHERE monitor_key=$1 AND bucket_start < $2
                       ORDER BY bucket_start DESC LIMIT 1""",
                    monitor_key, bucket,
                )
                # Historical data affects the new decision; verify its full
                # persisted receipt before using it as evidence.
                if older is not None:
                    _format(monitor_key, older["bucket_start"], older, inserted=False)
                previous = older["observation"] if older else None
                if isinstance(previous, str):
                    previous = json.loads(previous)
                decision = decide(observation, self.policy, previous)
                encoded = json.dumps(
                    {"monitor_key": monitor_key, "bucket_start": bucket.isoformat(),
                     "observation": observation, "decision": decision},
                    sort_keys=True, separators=(",", ":"), allow_nan=False,
                )
                digest = hashlib.sha256(encoded.encode()).hexdigest()
                saved = await con.fetchrow(
                    """INSERT INTO dragonzpyder_local_observations
                       (monitor_key,bucket_start,observed_at,observation,decision,receipt_sha256)
                       VALUES($1,$2,$3,$4::jsonb,$5::jsonb,$6)
                       RETURNING observation,decision,receipt_sha256""",
                    monitor_key, bucket, when,
                    json.dumps(observation, allow_nan=False),
                    json.dumps(decision, allow_nan=False), digest,
                )
                return _format(monitor_key, bucket, saved, inserted=True)


def _format(monitor_key: str, bucket: datetime, row, *, inserted: bool) -> dict:
    """Verify the persisted observation and decision before reporting success."""
    observation = row["observation"]
    decision = row["decision"]
    if isinstance(observation, str):
        observation = json.loads(observation)
    if isinstance(decision, str):
        decision = json.loads(decision)
    encoded = json.dumps(
        {"monitor_key": monitor_key, "bucket_start": bucket.isoformat(),
         "observation": observation, "decision": decision},
        sort_keys=True, separators=(",", ":"), allow_nan=False,
    )
    digest = hashlib.sha256(encoded.encode()).hexdigest()
    if not isinstance(row["receipt_sha256"], str) or not __import__("hmac").compare_digest(
        digest, row["receipt_sha256"]
    ):
        raise RuntimeError("Local monitor receipt integrity mismatch")
    return {
        "monitor_key": monitor_key,
        "bucket_start": bucket.isoformat(),
        "status": decision["status"],
        "alerts": decision["alerts"],
        "receipt_sha256": row["receipt_sha256"],
        "new_observation": inserted,
        "model_calls": 0,
        "external_tool_calls": 0,
    }


async def execute_local_monitor_tick(monitor_key: str = "worker-health") -> dict:
    require_monitor_gate()
    from asyncpg import create_pool
    pool = await create_pool(
        dsn=os.environ["DRAGONZPYDER_LOCAL_MONITOR_DATABASE_URL"],
        min_size=1, max_size=3,
    )
    try:
        async with pool.acquire() as con:
            if await con.fetchval(
                "SELECT to_regclass('dragonzpyder_local_observations')"
            ) is None:
                raise RuntimeError("Local monitor schema missing; run explicit migration")
        return await LocalMonitorAgent(pool, policy=policy_from_environment()).tick(
            monitor_key=monitor_key
        )
    finally:
        await pool.close()


def make_local_monitor_task(hatchet):
    """Define Hatchet execution without automatically creating recurring jobs."""
    @hatchet.task(
        name="dragonzpyder-local-health-v1",
        input_validator=LocalMonitorInput,
        retries=1,
        concurrency=1,
        execution_timeout=timedelta(seconds=45),
    )
    async def run(input: LocalMonitorInput, ctx) -> dict:
        return await execute_local_monitor_tick(input.monitor_key)
    return run


async def install_staging_monitor_cron(task, *, policy: MonitorPolicy | None = None):
    require_monitor_gate()
    if os.getenv("DRAGONZPYDER_LOCAL_MONITOR_CRON_INSTALL_ALLOWED") != "1":
        raise RuntimeError("Operator approval required before registering a cron")
    policy = policy or policy_from_environment()
    interval = policy.interval_minutes
    expression = "0 * * * *" if interval == 60 else f"*/{interval} * * * *"
    return await task.aio_create_cron(
        cron_name="dragonzpyder-staging-worker-health-v1",
        expression=expression,
        input=LocalMonitorInput(),
    )
