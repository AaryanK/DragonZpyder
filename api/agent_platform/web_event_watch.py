"""Operator-approved, scheduled web search -> durable event -> one-shot wake.

Uses DragonZpyder's existing fixed-origin, rate-bounded web search adapter.
Snapshot changes, the event inbox and the wake receipts are persisted in a
SINGLE PostgreSQL transaction: no lost wake if a worker crashes after update.
No client-supplied URLs, credentials, browser access or LLM calls.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from .goal_reconciler import utc_now, _canonical_time
from .monitor import canonical_sources, fingerprint, compare_sources
from .web_research import normalize_query, search_sources
from .event_wait import EventWaitStore

_MONITOR = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{2,63}$")
_MAX_PER_TICK = 2


def require_web_event_gate() -> None:
    if not all(os.getenv(name) == "1" for name in (
        "DRAGONZPYDER_WEB_EVENT_ENABLED",
        "DRAGONZPYDER_GOAL_SYNTHETIC_ONLY",
        "DRAGONZPYDER_AGENT_WEB_SEARCH_ENABLED",
    )) or os.getenv("DRAGONZPYDER_STAGE") != "staging":
        raise RuntimeError("Event web search requires isolated staging opt-in")


async def register_operator_watch(
    pool, *, monitor_id: str, query: str, interval_seconds: int = 600,
    now: datetime | None = None,
) -> dict:
    require_web_event_gate()
    if not isinstance(monitor_id, str) or not _MONITOR.fullmatch(monitor_id):
        raise ValueError("Invalid monitor identifier")
    query = normalize_query(query)
    if not isinstance(interval_seconds, int) or not 300 <= interval_seconds <= 86400:
        raise ValueError("Web monitor interval must be 5 minutes to 24 hours")
    clock = _canonical_time(now or utc_now())
    digest = hashlib.sha256(("wikipedia\x00" + query).encode()).hexdigest()
    async with pool.acquire() as con:
        async with con.transaction():
            row = await con.fetchrow(
                """INSERT INTO dragonzpyder_event_watches
                   (monitor_id,query,provider,query_sha256,next_check_at,
                    check_interval_seconds)
                   VALUES($1,$2,'wikipedia',$3,$4,$5)
                   ON CONFLICT (monitor_id) DO NOTHING
                   RETURNING monitor_id,query_sha256,checks""",
                monitor_id, query, digest, clock, interval_seconds,
            )
            if row is None:
                row = await con.fetchrow(
                    """SELECT monitor_id,query_sha256,checks
                       FROM dragonzpyder_event_watches WHERE monitor_id=$1
                       FOR UPDATE""", monitor_id,
                )
            if row is None or row["query_sha256"] != digest:
                raise ValueError("Monitor ID already belongs to a different query")
    return {"monitor_id": monitor_id, "provider": "wikipedia",
            "checks": row["checks"], "next_action": "scheduled_check",
            "model_calls": 0}


async def check_web_watch(
    pool, monitor_id: str, *, search=search_sources,
    now: datetime | None = None,
) -> dict:
    require_web_event_gate()
    clock = _canonical_time(now or utc_now())
    if not isinstance(monitor_id, str) or not _MONITOR.fullmatch(monitor_id):
        raise ValueError("Invalid monitor identifier")
    async with pool.acquire() as con:
        row = await con.fetchrow(
            """SELECT query,provider,check_interval_seconds,active
               FROM dragonzpyder_event_watches WHERE monitor_id=$1""",
            monitor_id,
        )
    if row is None or row["active"] is not True or row["provider"] != "wikipedia":
        raise LookupError("No active approved web monitor")

    # External I/O occurs outside the DB transaction; failure never modifies
    # snapshot state or publishes a fabricated event. Search has a hard timeout.
    observation = await search(row["query"], provider="wikipedia", limit=3)
    sources = canonical_sources(observation)
    if not sources:
        async with pool.acquire() as con:
            await con.execute(
                """UPDATE dragonzpyder_event_watches
                   SET next_check_at=$2,checked_at=$3
                   WHERE monitor_id=$1 AND active=true""",
                monitor_id, clock + timedelta(seconds=row["check_interval_seconds"]), clock,
            )
        return {"monitor_id": monitor_id, "status": "no_results",
                "event_published": False, "wakes_created": 0}

    digest = fingerprint(sources)
    async with pool.acquire() as con:
        async with con.transaction():
            prior = await con.fetchrow(
                """SELECT last_fingerprint,last_sources,checks,check_interval_seconds
                   FROM dragonzpyder_event_watches
                   WHERE monitor_id=$1 AND active=true FOR UPDATE""",
                monitor_id,
            )
            if prior is None:
                raise LookupError("Web monitor disabled during search")
            prev = prior["last_sources"]
            if isinstance(prev, str):
                prev = json.loads(prev)
            baseline = prior["checks"] == 0
            changed = (not baseline and prior["last_fingerprint"] != digest)
            diff = compare_sources(prev, sources) if changed else None
            # Source snapshots and resulting event/wakes live in the same DB,
            # updated atomically. A retry cannot silently drop a changed event.
            await con.execute(
                """UPDATE dragonzpyder_event_watches SET
                   last_fingerprint=$2,last_sources=$3::jsonb,checks=checks+1,
                   checked_at=$4,next_check_at=$5
                   WHERE monitor_id=$1""",
                monitor_id, digest, json.dumps(sources), clock,
                clock + timedelta(seconds=prior["check_interval_seconds"]),
            )
            event_id = None
            created = 0
            if changed:
                event_id = await con.fetchval(
                    """INSERT INTO dragonzpyder_event_inbox
                       (event_id,monitor_id,fingerprint,observed_at)
                       VALUES($1,$2,$3,$4)
                       ON CONFLICT(monitor_id,fingerprint) DO NOTHING
                       RETURNING event_id""",
                    uuid4(), monitor_id, digest, clock,
                )
                if event_id is not None:
                    waits = await con.fetch(
                        """SELECT wait_id,source_app
                           FROM dragonzpyder_event_waits
                           WHERE monitor_id=$1 AND status='armed'
                           ORDER BY created_at,wait_id
                           FOR UPDATE""", monitor_id,
                    )
                    for wait in waits:
                        status = ("pending" if wait["source_app"] == "internal_canary"
                                  else "awaiting_authorization")
                        inserted = await con.fetchval(
                            """INSERT INTO dragonzpyder_event_wakes
                               (wake_id,wait_id,event_id,status)
                               VALUES($1,$2,$3,$4)
                               ON CONFLICT(wait_id,event_id) DO NOTHING
                               RETURNING wake_id""",
                            uuid4(), wait["wait_id"], event_id, status,
                        )
                        if inserted is not None:
                            created += 1
                            await con.execute(
                                """UPDATE dragonzpyder_event_waits
                                   SET status='delivered' WHERE wait_id=$1
                                     AND status='armed'""",
                                wait["wait_id"],
                            )

    return {
        "monitor_id": monitor_id,
        "status": "baseline_created" if baseline else
                  ("changed" if changed else "unchanged"),
        "event_published": event_id is not None,
        "wakes_created": created,
        "source_count": len(sources),
        "diff": diff,
        "model_calls": 0,
    }


async def run_due_web_checks(
    pool, *, search=search_sources, now: datetime | None = None,
    max_checks: int = _MAX_PER_TICK,
) -> dict:
    require_web_event_gate()
    if not isinstance(max_checks, int) or not 1 <= max_checks <= _MAX_PER_TICK:
        raise ValueError("Web search check budget exceeded")
    clock = _canonical_time(now or utc_now())
    async with pool.acquire() as con:
        ids = await con.fetch(
            """SELECT monitor_id FROM dragonzpyder_event_watches
               WHERE active=true AND next_check_at <= $1
               ORDER BY next_check_at,monitor_id LIMIT $2""",
            clock, max_checks,
        )
    results = []
    for row in ids:
        # Search/provider failure bubbles up to Hatchet's bounded retry; it
        # cannot publish an event or rewrite the last good snapshot.
        results.append(await check_web_watch(
            pool, row["monitor_id"], search=search, now=clock,
        ))
    # A web snapshot change may insert a wait receipt. Completing an internal
    # canary wake does not call a model, use the network, or operate user tools.
    woken = await EventWaitStore(pool).drain_canary(now=clock)
    return {"checks": results, "wakes": woken,
            "model_calls": 0, "personal_tool_calls": 0}
