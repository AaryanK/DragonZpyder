"""Real PostgreSQL end-to-end test of the OAuth connection state machine.

Only OAuth server and MCP SDK calls are simulated. Database transactions,
row-level refresh locking and encryption run against real PostgreSQL.
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import asyncpg
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent_platform import mcp_connections as module
from agent_platform.mcp_broker import CatalogGrant, McpGrant
from agent_platform.mcp_managed_catalog import ManagedMcpRunCatalog
from test_mcp_connections import FakeOAuth, META, env


def test_real_postgres_oauth_lifecycle_and_concurrent_refresh(monkeypatch):
    dsn = os.getenv("MCP_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("No isolated PostgreSQL testing DSN")
    env(monkeypatch)
    from cryptography.fernet import Fernet
    monkeypatch.setenv("DRAGONZPYDER_MCP_FERNET_KEYS", Fernet.generate_key().decode())
    monkeypatch.setattr(module, "discover_oauth",
                        lambda *args: asyncio.sleep(0, result=META))
    monkeypatch.setattr("authlib.integrations.httpx_client.AsyncOAuth2Client", FakeOAuth)
    FakeOAuth.exchanges.clear()
    FakeOAuth.revocations.clear()
    FakeOAuth.refreshes = 0

    async def run():
        pool = await asyncpg.create_pool(dsn, min_size=1, max_size=6)
        try:
            async with pool.acquire() as db:
                await db.execute("DROP TABLE IF EXISTS dz_mcp_goal_selections")
                await db.execute("DROP TABLE IF EXISTS dz_mcp_connections")
                await db.execute("DROP TABLE IF EXISTS dz_mcp_oauth_attempts")
                await db.execute("DROP TABLE IF EXISTS dz_mcp_oauth_clients")
                migration = (
                    Path(__file__).resolve().parents[1] /
                    "agent_platform/migrations/20261122_mcp_connections.sql"
                ).read_text()
                await db.execute(migration)
            manager = module.OAuthConnectionManager(
                pool, module.CredentialCipher(), http=object(),
            )

            async def connect(user, provider):
                session = "s" * 40
                url = await manager.begin(owner=user, session_secret=session,
                                          provider_id=provider)
                state = parse_qs(urlsplit(url).query)["state"][0]
                return (await manager.finish(
                    owner=user, session_secret=session, state=state, code="code"
                ))["connection_id"]

            one = await connect("alice", "archive")
            two = await connect("alice", "library")
            other = await connect("bob", "archive")
            assert len({one, two, other}) == 3
            async with pool.acquire() as db:
                raw = await db.fetchval(
                    "SELECT encrypted_tokens FROM dz_mcp_connections WHERE public_alias=$1", one,
                )
                assert b"secret-long-access-token-000" not in bytes(raw)
                assert await db.fetchval(
                    "SELECT count(*) FROM dz_mcp_oauth_attempts"
                ) == 0
                await db.execute(
                    """UPDATE dz_mcp_connections SET access_expires_at=now()-interval '5 seconds'
                       WHERE public_alias=$1""", one,
                )

            # Actual row-level FOR UPDATE mutex across different pool connections.
            grants = await asyncio.gather(*[
                manager.grant(owner="alice", alias=one,
                              capability="lookup", authorized=True)
                for _ in range(12)
            ])
            assert len(grants) == 12
            assert FakeOAuth.refreshes == 1
            assert all("secret-long-new-token-111" in
                       g.headers["Authorization"] for g in grants)

            class FakeTool:
                def __init__(self, name, bearer):
                    self.name = name
                    self.description = "Records " + bearer
                    self.args_schema = {
                        "type": "object", "properties": {"q": {"type": "string"}},
                        "required": ["q"],
                    }
                    self.bearer = bearer

                async def ainvoke(self, arguments):
                    return {"items": [arguments["q"]], "echo": self.bearer}

            async def discover(grants, max_tools=1):
                g = grants[0]
                return [FakeTool(g.provider_id + "_lookup",
                                 g.headers["Authorization"][7:])]
            monkeypatch.setattr(
                "agent_platform.mcp_managed_catalog.discover_granted_mcp_tools",
                discover,
            )
            entries = []
            for alias, provider in ((one, "archive"), (two, "library")):
                host = provider + ".example.com"
                entries.append(CatalogGrant(
                    McpGrant(alias, "https://" + host + "/mcp",
                             frozenset({host}), {}, frozenset({"lookup"})),
                    frozenset({"lookup"}), "Search records",
                ))
            catalog = ManagedMcpRunCatalog(
                entries, owner="alice", manager=manager, scheduled=True,
            )
            assert len(catalog.search("lookup")) == 2
            for alias in (one, two):
                desc = await catalog.describe(alias, "lookup")
                outcome = await catalog.invoke(
                    alias, "lookup", {"q": "science"}, desc["schema_sha256"],
                )
                assert outcome["result"]["items"] == ["science"]
                assert outcome["result"]["echo"] == "[redacted credential]"

            with pytest.raises(module.ConnectionDenied):
                await manager.grant(owner="bob", alias=one,
                                    capability="lookup", authorized=True)
            with pytest.raises(module.ConnectionDenied):
                await manager.grant(owner="alice", alias=other,
                                    capability="lookup", authorized=True)

            assert await manager.disconnect("alice", one)
            with pytest.raises(module.ConnectionDenied):
                await catalog.describe(one, "lookup")
            assert (await manager.list_connections("alice"))[0]["status"] in (
                "active", "revoked",
            )
            async with pool.acquire() as db:
                assert await db.fetchval(
                    "SELECT encrypted_tokens FROM dz_mcp_connections WHERE public_alias=$1", one,
                ) is None
                await db.execute(
                    """INSERT INTO dz_mcp_goal_selections(goal_id,owner_id,selection_hash)
                       VALUES($1,$2,$3)""", "goal1", "alice", "a" * 64,
                )
                assert await db.fetchval(
                    "SELECT selection_hash FROM dz_mcp_goal_selections WHERE goal_id='goal1'"
                ) == "a" * 64
        finally:
            await pool.close()

    asyncio.run(run())
