"""Offline and disposable real PostgreSQL tests for the pending-only importer."""
import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import asyncpg
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from identity.importer import prepare_snapshot
from identity.production_import import ApprovedInventory, import_pending_production, read_source_snapshot
from identity.reconciliation import IdentityMigrationConflict

def rows():
    u1,u2 = str(uuid4()),str(uuid4())
    return [
        {"id":u1,"email":"one@example.test","password_hash":None,"display_name":"One",
         "email_verified_at":datetime(2025,1,1),"active":True},
        {"id":u2,"email":"two@example.test","password_hash":None,"display_name":"Two",
         "email_verified_at":None,"active":False},
    ], [{"user_id":u1,"provider":"google","provider_subject":"synthetic-google"}]

class Source:
    def __init__(self, users, links): self.users=users; self.links=links
    def transaction(self, **kwargs):
        assert kwargs == {"isolation":"repeatable_read","readonly":True}
        class Tx:
            async def __aenter__(self): return self
            async def __aexit__(self,*args): return False
        return Tx()
    async def fetchval(self, query): return True
    async def fetch(self, query):
        if "FROM public.app_users" in query: return self.users
        assert "WHERE provider='google'" in query
        return self.links

@pytest.mark.asyncio
async def test_readonly_source_and_inventory_drift():
    users, links=rows()
    bundle=await read_source_snapshot(Source(users,links),ApprovedInventory(2,1))
    assert bundle.counts()=={"accounts":2,"provider_links":1}
    assert bundle.accounts[0].subject in {u["id"] for u in users}
    assert next(a for a in bundle.accounts if a.email_verified_at).email_verified_at.utcoffset().total_seconds()==0
    with pytest.raises(IdentityMigrationConflict):
        await read_source_snapshot(Source(users,links),ApprovedInventory(3,1))

@pytest.mark.asyncio
async def test_import_fails_without_both_approvals(monkeypatch):
    users, links=rows()
    bundle=await read_source_snapshot(Source(users,links),ApprovedInventory(2,1))
    monkeypatch.delenv("DRAGONZPYDER_IDENTITY_PRODUCTION_IMPORT",raising=False)
    with pytest.raises(PermissionError):
        await import_pending_production(None,bundle,ApprovedInventory(2,1),operator_approved=True)
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_PRODUCTION_IMPORT","1")
    with pytest.raises(PermissionError):
        await import_pending_production(None,bundle,ApprovedInventory(2,1))

@pytest.mark.asyncio
async def test_import_refuses_discord_as_native_login(monkeypatch):
    users, links=rows()
    links[0]["provider"]="discord"
    bundle=prepare_snapshot(users,links,[])
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_PRODUCTION_IMPORT","1")
    with pytest.raises(IdentityMigrationConflict):
        await import_pending_production(None,bundle,ApprovedInventory(2,1),operator_approved=True)

@pytest.mark.asyncio
async def test_pending_import_real_postgres_disposable_only(monkeypatch):
    dsn=os.getenv("DRAGONZPYDER_IDENTITY_TEST_DSN","")
    if not dsn:
        pytest.skip("No disposable identity_test PostgreSQL")
    if urlsplit(dsn).path!="/identity_test":
        raise RuntimeError("Never run against non-disposable database")
    users, links=rows()
    bundle=await read_source_snapshot(Source(users,links),ApprovedInventory(2,1))
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_PRODUCTION_IMPORT","1")
    conn=await asyncpg.connect(dsn)
    tx=conn.transaction()
    await tx.start()
    try:
        assert not await conn.fetchval("SELECT to_regclass('public.identity_accounts') IS NOT NULL")
        sql=(Path(__file__).resolve().parents[1]/"identity"/"schema_bootstrap_manual.sql").read_text("utf-8")
        await conn.execute(sql.replace("BEGIN;\nSET LOCAL","SET LOCAL",1).removesuffix("COMMIT;\n"))
        result=await import_pending_production(conn,bundle,ApprovedInventory(2,1),operator_approved=True)
        assert result=={"accounts":2,"provider_links":1,"active_accounts":0}
        assert await conn.fetchval("SELECT count(*) FROM identity_accounts WHERE subject=source_operly_user_id AND status='pending'")==2
        with pytest.raises(IdentityMigrationConflict):
            await import_pending_production(conn,bundle,ApprovedInventory(2,1),operator_approved=True)
        with pytest.raises(asyncpg.CheckViolationError):
            async with conn.transaction():
                await conn.execute("UPDATE identity_accounts SET status='active'")
    finally:
        await tx.rollback()
        await conn.close()
