"""Staging-only, deterministic web-change monitoring.

No LLM is invoked for routine checks. Hatchet supplies the cron; PostgreSQL
holds the previous source snapshot so worker restarts do not lose state.
Only trusted operator-owned monitor IDs may be scheduled, never user-supplied
cron expressions or delegated account authority.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import timedelta
from typing import Literal

import asyncpg
from pydantic import BaseModel, Field

from .web_research import search_sources


class MonitorInput(BaseModel):
    monitor_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{3,64}$")
    query: str = Field(min_length=3, max_length=240)
    provider: Literal["wikipedia", "brave"] = "wikipedia"
    max_results: int = Field(default=3, ge=1, le=5)


DDL = """
CREATE TABLE IF NOT EXISTS dragonzpyder_staging_web_monitor (
    monitor_id text PRIMARY KEY,
    query_sha256 text NOT NULL,
    provider text NOT NULL,
    fingerprint text NOT NULL DEFAULT '',
    sources_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    checked_at timestamptz,
    checks bigint NOT NULL DEFAULT 0
);
"""


def canonical_sources(report: dict) -> list[dict]:
    sources = report.get("results", [])
    if not isinstance(sources, list):
        raise ValueError("Invalid search result")
    # Search rank is unstable. Only compare stable attributed content.
    seen = {}
    for source in sources:
        if not isinstance(source, dict):
            continue
        url, title = source.get("url"), source.get("title")
        if not isinstance(url, str) or not isinstance(title, str):
            continue
        seen[url] = {
            "url": url,
            "title": title[:200],
            "snippet": str(source.get("snippet") or "")[:700],
        }
    return [seen[key] for key in sorted(seen)]


def compare_sources(before: list, after: list) -> dict:
    a = {x["url"]: x for x in before}
    b = {x["url"]: x for x in after}
    return {
        "new": sorted(b.keys() - a.keys())[:5],
        "removed": sorted(a.keys() - b.keys())[:5],
        "updated": sorted(k for k in b.keys() & a.keys() if b[k] != a[k])[:5],
    }


def fingerprint(sources: list[dict]) -> str:
    normalized = json.dumps(sources, sort_keys=True, ensure_ascii=False,
                            separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


async def run_monitor(input: MonitorInput, *, search=search_sources,
                      connection_factory=None):
    # The DB and lookup principal are operator-only until user identity and
    # signed per-user capability delegation are integrated.
    if os.getenv("DRAGONZPYDER_WEB_MONITOR_ENABLED") != "1":
        raise RuntimeError("Staging web monitor is disabled")
    if os.getenv("DRAGONZPYDER_AGENT_WEB_SEARCH_ENABLED") != "1":
        raise RuntimeError("Web search is disabled")
    dsn = os.getenv("DRAGONZPYDER_AGENT_DATABASE_URL", "")
    if not dsn.startswith(("postgres://", "postgresql://")):
        raise RuntimeError("Persistent monitor database is not configured")
    report = await search(input.query, provider=input.provider, limit=input.max_results)
    current = canonical_sources(report)
    if not current:
        # Do NOT assume a failed/empty search means every page disappeared.
        return {"monitor_id": input.monitor_id, "status": "no_results",
                "changed": False, "source_count": 0, "diff": None}
    query_sha = hashlib.sha256(
        (input.provider + "\0" + input.query).encode("utf-8")
    ).hexdigest()
    digest = fingerprint(current)
    connector = connection_factory or asyncpg.connect
    conn = await connector(dsn, command_timeout=7)
    try:
        await conn.execute(DDL)
        async with conn.transaction():
            await conn.execute(
                """INSERT INTO dragonzpyder_staging_web_monitor
                   (monitor_id,query_sha256,provider)
                   VALUES($1,$2,$3) ON CONFLICT DO NOTHING""",
                input.monitor_id, query_sha, input.provider,
            )
            old = await conn.fetchrow(
                """SELECT query_sha256,fingerprint,sources_json,checks
                   FROM dragonzpyder_staging_web_monitor
                   WHERE monitor_id=$1 FOR UPDATE""", input.monitor_id,
            )
            if old["query_sha256"] != query_sha:
                raise ValueError("Monitor ID is already assigned to a different query")
            previous = old["sources_json"]
            if isinstance(previous, str):
                previous = json.loads(previous)
            if not isinstance(previous, list):
                previous = []
            initial = old["checks"] == 0
            changes = compare_sources(previous, current) if not initial else {
                "new": [], "removed": [], "updated": [],
            }
            changed = (not initial and old["fingerprint"] != digest)
            await conn.execute(
                """UPDATE dragonzpyder_staging_web_monitor SET
                   fingerprint=$2,sources_json=$3::jsonb,
                   checked_at=now(),checks=checks+1
                   WHERE monitor_id=$1""",
                input.monitor_id, digest, json.dumps(current),
            )
    finally:
        await conn.close()
    return {
        "monitor_id": input.monitor_id,
        "status": "baseline_created" if initial else ("changed" if changed else "unchanged"),
        "changed": changed, "source_count": len(current),
        "diff": changes if changed else {"new": [], "removed": [], "updated": []},
        "sources": [{"title": x["title"], "url": x["url"]} for x in current],
        "provider": input.provider,
    }


def make_monitor_task(hatchet):
    """Register a Hatchet task; this does NOT create any recurring cron."""
    @hatchet.task(
        name="dragonzpyder-staging-web-monitor",
        input_validator=MonitorInput,
        concurrency=1,
        retries=0,
        execution_timeout=timedelta(seconds=45),
    )
    async def check(input: MonitorInput, ctx) -> dict:
        return await run_monitor(input)

    return check
