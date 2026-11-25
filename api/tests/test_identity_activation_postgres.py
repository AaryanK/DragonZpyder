"""Disposable PostgreSQL contract for operator-only imported account activation."""
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import pytest

DSN = os.getenv("DRAGONZPYDER_IDENTITY_TEST_DSN", "")
pytestmark = [pytest.mark.asyncio, pytest.mark.skipif(not DSN, reason="No disposable identity_test PostgreSQL")]
ROOT = Path(__file__).resolve().parents[1] / "identity"
sys.path.insert(0, str(ROOT.parent))


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
            for subject in (a,b,c):
                with pytest.raises(asyncpg.RaiseError):
                    await conn.execute("SELECT public.approve_imported_identity($1,$2)",subject,uuid4())
            expired = uuid4()
            await conn.execute("INSERT INTO public.identity_import_proofs(proof_id,subject,proof_method,proved_at) VALUES($1,$2,'password',now()-interval '16 minutes')",expired,a)
            with pytest.raises(asyncpg.RaiseError):
                await conn.execute("SELECT public.approve_imported_identity($1,$2)",a,expired)
            assert not await conn.fetchval("SELECT has_function_privilege('dz_identity_api','public.approve_imported_identity(text,uuid)','EXECUTE')")
            assert not await conn.fetchval("SELECT has_column_privilege('dz_identity_api','public.identity_accounts','import_activation_receipt_id','UPDATE')")
            assert not await conn.fetchval("SELECT has_table_privilege('dz_identity_api','public.identity_import_activation_receipts','INSERT')")
            from fastapi import HTTPException
            from identity.http_bridge import _restricted_identity_role
            # The runtime accepts the original least-privilege role after the
            # new schema, but rejects an accidental grant of activation authority.
            await conn.execute("SET SESSION AUTHORIZATION dz_identity_api")
            try:
                await _restricted_identity_role(conn)
            finally:
                await conn.execute("RESET SESSION AUTHORIZATION")
            await conn.execute("GRANT UPDATE (import_activation_receipt_id) ON public.identity_accounts TO dz_identity_api")
            await conn.execute("SET SESSION AUTHORIZATION dz_identity_api")
            try:
                with pytest.raises(HTTPException):
                    await _restricted_identity_role(conn)
            finally:
                await conn.execute("RESET SESSION AUTHORIZATION")
            await conn.execute("REVOKE UPDATE (import_activation_receipt_id) ON public.identity_accounts FROM dz_identity_api")
            receipt = uuid4()
            await conn.execute("SET SESSION AUTHORIZATION dz_identity_api")
            try:
                await conn.execute("INSERT INTO public.identity_import_proofs(proof_id,subject,proof_method) VALUES($1,$2,'password')",receipt,a)
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    await conn.execute("INSERT INTO public.identity_import_proofs(proof_id,subject,proof_method) VALUES($1,$2,'password')",uuid4(),c)
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    await conn.execute("UPDATE public.identity_import_proofs SET proved_at=now()")
            finally:
                await conn.execute("RESET SESSION AUTHORIZATION")
            with pytest.raises(asyncpg.RaiseError):
                await conn.execute("SELECT public.approve_imported_identity($1,$2)",b,receipt)
            await conn.execute("SELECT public.approve_imported_identity($1,$2)",a,receipt)
            assert await conn.fetchval("SELECT status FROM public.identity_accounts WHERE subject=$1",a) == "active"
            assert await conn.fetchval("SELECT import_activation_receipt_id FROM public.identity_accounts WHERE subject=$1",a) == receipt
            with pytest.raises(asyncpg.ForeignKeyViolationError):
                await conn.execute("UPDATE public.identity_accounts SET status='active',import_activation_receipt_id=$1 WHERE subject=$2",receipt,b)
            with pytest.raises(asyncpg.RaiseError):
                await conn.execute("SELECT public.approve_imported_identity($1,$2)",a,receipt)
            assert await conn.fetchval("SELECT count(*) FROM public.identity_import_activation_receipts") == 1
            assert await conn.fetchval("SELECT count(*) FROM public.identity_accounts WHERE status='pending'") == 2
        finally:
            await conn.execute("""
                DROP FUNCTION IF EXISTS public.approve_imported_identity(text,uuid);
                DROP TABLE IF EXISTS public.identity_import_activation_receipts, public.identity_import_proofs,
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
