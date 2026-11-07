"""Private infrastructure probes and synthetic memory acceptance tests.

No user content is retained or requested by these helpers.
"""
from __future__ import annotations

import asyncio
import os
import secrets

import httpx


async def hatchet_readiness() -> str:
    url = os.getenv("DRAGONZPYDER_HATCHET_READINESS_URL", "").strip()
    # Restrict staging probes to the explicitly provisioned internal endpoint.
    if url != "http://hatchet.railway.internal:8888/api/ready":
        return "not_configured"
    try:
        async with httpx.AsyncClient(timeout=4, trust_env=False) as http:
            response = await http.get(url, follow_redirects=False)
        return "server_online" if response.status_code == 200 else "server_unhealthy"
    except (httpx.HTTPError, TimeoutError):
        return "server_unreachable"


async def vector_readiness() -> str:
    dsn = os.getenv("DRAGONZPYDER_MEMORY_DATABASE_URL")
    if not dsn:
        return "not_configured"
    try:
        from psycopg import AsyncConnection
        async with await asyncio.wait_for(
            AsyncConnection.connect(dsn, connect_timeout=4), timeout=5
        ) as con:
            async with con.cursor() as cur:
                await cur.execute("SELECT count(*) FROM pg_extension WHERE extname = 'vector'")
                row = await cur.fetchone()
        return "pgvector_ready" if row and row[0] == 1 else "pgvector_missing"
    except Exception:
        return "database_unreachable"


def synthetic_memory_smoke() -> dict:
    """Exercise Mem0 add/search/delete for a random, nonpersonal test principal."""
    from agent_platform.memory import PersonalMemory

    user = "staging-smoke-" + secrets.token_hex(12)
    memory = PersonalMemory()
    written = False
    found = False
    deleted = False
    try:
        memory.remember(
            user_id=user, consent=True,
            text="Synthetic acceptance test fact: the pretend lighthouse is amber.",
        )
        written = True
        results = memory.search(
            user_id=user, query="What is the color of the pretend lighthouse?"
        )
        items = results.get("results", []) if isinstance(results, dict) else results
        if not isinstance(items, list):
            items = []
        found = any("amber" in str(item).lower() for item in items)
    finally:
        memory.delete_user(user_id=user)
        deleted = True
    return {"memory_written": written, "memory_retrieved": found, "synthetic_data_deleted": deleted}
