import sys
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import replace
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from identity.importer import prepare_snapshot
from identity.production_import import ApprovedInventory
from identity.recovery_delta import plan_recovery_additions
from identity.reconciliation import IdentityMigrationConflict


def sample():
    u = {"id": str(uuid4()), "email": "recovery@example.test",
         "display_name": "Recovery", "password_hash": None, "active": True,
         "email_verified_at": datetime.now(timezone.utc)}
    return prepare_snapshot([u], [], [])


def changed(bundle, **kwargs):
    return replace(bundle, accounts=(replace(bundle.accounts[0], **kwargs),))


def test_recovery_addition_only():
    target = sample()
    source = changed(target,password_hash="pbkdf2_sha256$synthetic")
    approved = ApprovedInventory(1,0)
    assert not plan_recovery_additions(target,target,approved)
    result = plan_recovery_additions(source,target,approved)
    assert len(result)==1 and result[0].subject==target.accounts[0].subject
    assert "synthetic" not in repr(result)
    with pytest.raises(IdentityMigrationConflict):
        plan_recovery_additions(target,source,approved)
    with pytest.raises(IdentityMigrationConflict):
        plan_recovery_additions(changed(source,password_hash="$argon2id$other"),source,approved)


@pytest.mark.parametrize("field,value", [
    ("email","another@example.test"),("display_name","Different"),
    ("source_active",False),("email_verified_at",None),
])
def test_drift_rejected(field,value):
    target=sample()
    source=changed(target,password_hash="$argon2id$synthetic",**{field:value})
    with pytest.raises(IdentityMigrationConflict):
        plan_recovery_additions(source,target,ApprovedInventory(1,0))


def test_unverified_and_inactive_recovery_rejected():
    for target in (changed(sample(),email_verified_at=None),changed(sample(),source_active=False)):
        source=changed(target,password_hash="$argon2id$synthetic")
        with pytest.raises(IdentityMigrationConflict):
            plan_recovery_additions(source,target,ApprovedInventory(1,0))


@pytest.mark.asyncio
async def test_recovery_sync_disposable_postgres(monkeypatch):
    import os
    import asyncpg
    from urllib.parse import urlsplit
    from identity.recovery_delta import apply_pending_recovery_additions
    from identity.passwords import hash_password
    dsn=os.getenv("DRAGONZPYDER_IDENTITY_TEST_DSN","")
    if not dsn:
        pytest.skip("No disposable identity_test PostgreSQL")
    if urlsplit(dsn).path!="/identity_test":
        raise RuntimeError("Never run against non-disposable database")
    conn=await asyncpg.connect(dsn)
    root=Path(__file__).resolve().parents[1]/"identity"
    target=sample()
    account=target.accounts[0]
    source=changed(target,password_hash=hash_password("synthetic-recovery-password"))
    approved=ApprovedInventory(1,0)
    try:
        assert await conn.fetchval("SELECT to_regclass('public.identity_accounts') IS NULL")
        await conn.execute((root/"schema_bootstrap_manual.sql").read_text())
        await conn.execute((root/"schema_role_manual.sql").read_text())
        try:
            await conn.execute("""
                INSERT INTO public.identity_accounts(subject,source_operly_user_id,email,display_name,
                     password_hash,email_verified_at,source_active,status)
                VALUES($1,$1,$2,$3,NULL,$4,TRUE,'pending')
            """,account.subject,account.email,account.display_name,account.email_verified_at)
            await conn.execute((root/"schema_recovery_sync_role_manual.sql").read_text())
            monkeypatch.setenv("DRAGONZPYDER_RECOVERY_SYNC_APPROVED","1")
            await conn.execute("SET SESSION AUTHORIZATION dz_identity_recovery_sync")
            try:
                with pytest.raises(IdentityMigrationConflict):
                    await apply_pending_recovery_additions(conn,source,approved,expected_additions=0,operator_approved=True)
                result=await apply_pending_recovery_additions(conn,source,approved,expected_additions=1,operator_approved=True)
                assert result=={"password_additions":1,"active_accounts":0}
                assert await conn.execute("UPDATE public.identity_accounts SET password_hash=$1",hash_password("different-synthetic-password"))=="UPDATE 0"
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    await conn.execute("UPDATE public.identity_accounts SET status='active'")
                with pytest.raises(IdentityMigrationConflict):
                    await apply_pending_recovery_additions(conn,changed(source,password_hash=hash_password("other-password")),approved,expected_additions=1,operator_approved=True)
                assert await apply_pending_recovery_additions(conn,source,approved,expected_additions=0,operator_approved=True)=={"password_additions":0,"active_accounts":0}
            finally:
                await conn.execute("RESET SESSION AUTHORIZATION")
            assert await conn.fetchval("SELECT password_hash FROM public.identity_accounts")==source.accounts[0].password_hash
            assert await conn.fetchval("SELECT status FROM public.identity_accounts")=="pending"
        finally:
            await conn.execute("""
                DROP TABLE public.identity_authorization_interactions,public.identity_provider_challenges,
                    public.identity_login_rate_limits,public.identity_refresh_grants,
                    public.identity_authorization_codes,public.identity_browser_sessions,
                    public.identity_provider_links,public.identity_oauth_clients,public.identity_accounts;
                DROP OWNED BY dz_identity_recovery_sync;
                DROP ROLE dz_identity_recovery_sync;
                DROP OWNED BY dz_identity_api;
                DROP ROLE dz_identity_api;
            """)
    finally:
        await conn.close()
