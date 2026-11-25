"""Disposable PostgreSQL contract for operator-only imported account activation."""
import os
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import pytest

DSN = os.getenv("DRAGONZPYDER_IDENTITY_TEST_DSN", "")
pytestmark = [pytest.mark.asyncio, pytest.mark.skipif(not DSN, reason="No disposable identity_test PostgreSQL")]
ROOT = Path(__file__).resolve().parents[1] / "identity"


async def test_activation_receipt_fence():
    import asyncpg
    if urlsplit(DSN).path != "/identity_test":
        raise RuntimeError("Never run against non-disposable database")
    conn = await asyncpg.connect(DSN)
    try:
        assert await conn.fetchval("SELECT to_regclass('public.identity_accounts') IS NULL")
        assert await conn.fetchval("SELECT NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='dz_identity_api')")
        await conn.execute((ROOT / "schema_bootstrap_manual.sql").read_text())
        await conn.execute((ROOT / "schema_role_manual.sql").read_text())
        try:
            a, b, c = [str(uuid4()) for _ in range(3)]
            for subject, email, password, active in [
                (a, "a@example.test", "pbkdf2_sha256$synthetic", True),
                (b, "b@example.test", None, True),
                (c, "c@example.test", "pbkdf2_sha256$synthetic", False),
            ]:
                await conn.execute("""
                    INSERT INTO public.identity_accounts
                    (subject,source_operly_user_id,email,display_name,password_hash,source_active,status)
                    VALUES($1,$1,$2,'Synthetic',$3,$4,'pending')
                """, subject, email, password, active)
            await conn.execute((ROOT / "schema_import_activation_review.sql").read_text())
            assert await conn.fetchval("SELECT count(*) FROM public.identity_accounts WHERE status='active'") == 0
            with pytest.raises(asyncpg.CheckViolationError):
                await conn.execute("UPDATE public.identity_accounts SET status='active' WHERE subject=$1", a)
            for subject, method in [(b,"password"), (c,"password"), (b,"google"), (b,"legacy_reauth")]:
                with pytest.raises(asyncpg.RaiseError):
                    await conn.execute("SELECT public.approve_imported_identity($1,$2,$3,now())",subject,uuid4(),method)
            with pytest.raises(asyncpg.RaiseError):
                await conn.execute("SELECT public.approve_imported_identity($1,$2,'password',now()-interval '16 minutes')",a,uuid4())
            assert not await conn.fetchval("SELECT has_function_privilege('dz_identity_api','public.approve_imported_identity(text,uuid,text,timestamptz)','EXECUTE')")
            assert not await conn.fetchval("SELECT has_column_privilege('dz_identity_api','public.identity_accounts','import_activation_receipt_id','UPDATE')")
            assert not await conn.fetchval("SELECT has_table_privilege('dz_identity_api','public.identity_import_activation_receipts','INSERT')")
            receipt = uuid4()
            await conn.execute("SELECT public.approve_imported_identity($1,$2,'password',now())",a,receipt)
            assert await conn.fetchval("SELECT status FROM public.identity_accounts WHERE subject=$1",a) == "active"
            assert await conn.fetchval("SELECT import_activation_receipt_id FROM public.identity_accounts WHERE subject=$1",a) == receipt
            with pytest.raises(asyncpg.ForeignKeyViolationError):
                await conn.execute("UPDATE public.identity_accounts SET status='active',import_activation_receipt_id=$1 WHERE subject=$2",receipt,b)
            with pytest.raises(asyncpg.RaiseError):
                await conn.execute("SELECT public.approve_imported_identity($1,$2,'password',now())",a,uuid4())
            assert await conn.fetchval("SELECT count(*) FROM public.identity_import_activation_receipts") == 1
            assert await conn.fetchval("SELECT count(*) FROM public.identity_accounts WHERE status='pending'") == 2
        finally:
            await conn.execute("""
                DROP FUNCTION IF EXISTS public.approve_imported_identity(text,uuid,text,timestamptz);
                DROP TABLE IF EXISTS public.identity_import_activation_receipts,
                  public.identity_authorization_interactions, public.identity_provider_challenges,
                  public.identity_login_rate_limits, public.identity_refresh_grants,
                  public.identity_authorization_codes, public.identity_browser_sessions,
                  public.identity_provider_links, public.identity_oauth_clients,
                  public.identity_accounts;
                DROP OWNED BY dz_identity_api;
                DROP ROLE dz_identity_api;
            """)
    finally:
        await conn.close()
