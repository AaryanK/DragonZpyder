"""Disposable PostgreSQL recovery tests. No real accounts or mail."""
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4
import pytest

ROOT=Path(__file__).resolve().parents[1]/"identity"
sys.path.insert(0,str(ROOT.parent))


@pytest.mark.asyncio
async def test_pending_recovery_authority_and_replay():
    import asyncpg
    from identity.passwords import hash_password
    dsn=os.getenv("DRAGONZPYDER_IDENTITY_TEST_DSN","")
    if not dsn: pytest.skip("No disposable PostgreSQL")
    if urlsplit(dsn).path!="/identity_test": raise RuntimeError("Never use production")
    conn=await asyncpg.connect(dsn)
    try:
        assert await conn.fetchval("SELECT to_regclass('public.identity_accounts') IS NULL")
        for name in ("schema_bootstrap_manual.sql","schema_role_manual.sql",
                     "schema_import_activation_review.sql","schema_native_pending_recovery_review.sql"):
            await conn.execute((ROOT/name).read_text())
        a,b,c=[str(uuid4()) for _ in range(3)]
        for sid,email,verified in [(a,"a@example.test",True),(b,"b@example.test",True),(c,"c@example.test",False)]:
            await conn.execute("""
                INSERT INTO public.identity_accounts(subject,source_operly_user_id,email,display_name,
                source_active,status,email_verified_at) VALUES($1,$1,$2,'Synthetic',TRUE,'pending',
                CASE WHEN $3 THEN now() ELSE NULL END)
            """,sid,email,verified)
        for sid,email in [(a,"a@example.test"),(c,"c@example.test")]:
            await conn.execute("INSERT INTO public.identity_recovery_authority(subject,email,expires_at) VALUES($1,$2,now()+interval '1 day')",sid,email)
        await conn.execute("SET SESSION AUTHORIZATION dz_identity_api")
        try:
            assert await conn.fetchval("SELECT public.issue_pending_recovery($1,$2)","b@example.test","b"*64) is None
            assert await conn.fetchval("SELECT public.issue_pending_recovery($1,$2)","c@example.test","c"*64) is None
            assert await conn.fetchval("SELECT public.issue_pending_recovery($1,$2)","a@example.test","a"*64)=="a@example.test"
            assert await conn.fetchval("SELECT public.issue_pending_recovery($1,$2)","a@example.test","d"*64)=="a@example.test"
            assert await conn.fetchval("SELECT public.issue_pending_recovery($1,$2)","a@example.test","e"*64)=="a@example.test"
            assert await conn.fetchval("SELECT public.issue_pending_recovery($1,$2)","a@example.test","f"*64) is None
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await conn.execute("UPDATE public.identity_recovery_authority SET revoked_at=now()")
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await conn.fetch("SELECT * FROM public.identity_recovery_challenges")
            hashed=hash_password("synthetic-safe-password")
            async def redeem(email, digest, proof):
                return await conn.fetchval("SELECT public.redeem_pending_recovery($1,$2,$3,$4)",email,digest,hashed,proof)
            assert not await redeem("b@example.test","a"*64,uuid4())
        finally:
            await conn.execute("RESET SESSION AUTHORIZATION")
        await conn.execute("UPDATE public.identity_recovery_challenges SET created_at=now()-interval '25 minutes',expires_at=now()-interval '5 minutes' WHERE token_hash=$1","d"*64)
        await conn.execute("SET SESSION AUTHORIZATION dz_identity_api")
        try:
            assert not await redeem("a@example.test","d"*64,uuid4())
            proof=uuid4()
            assert await redeem("a@example.test","a"*64,proof)
            assert not await redeem("a@example.test","a"*64,uuid4())
            assert not await redeem("a@example.test","e"*64,uuid4())
            assert await conn.fetchval("SELECT public.issue_pending_recovery($1,$2)","a@example.test","f"*64) is None
            assert await conn.fetchval("SELECT count(*) FROM public.identity_browser_sessions")==0
        finally:
            await conn.execute("RESET SESSION AUTHORIZATION")
        assert await conn.fetchval("SELECT status FROM public.identity_accounts WHERE subject=$1",a)=="pending"
        assert await conn.fetchval("SELECT password_hash FROM public.identity_accounts WHERE subject=$1",a)==hashed
        assert await conn.fetchval("SELECT subject FROM public.identity_import_proofs WHERE proof_id=$1",proof)==a
        assert await conn.fetchval("SELECT count(*) FROM public.identity_accounts WHERE password_hash IS NOT NULL")==1
    finally:
        await conn.execute("""
            DROP FUNCTION IF EXISTS public.issue_pending_recovery(text,text),
                public.redeem_pending_recovery(text,text,text,uuid),
                public.approve_imported_identity(text,uuid);
            DROP TABLE IF EXISTS public.identity_recovery_challenges,public.identity_recovery_authority,
                public.identity_import_activation_receipts,public.identity_import_proofs,
                public.identity_authorization_interactions,public.identity_provider_challenges,
                public.identity_login_rate_limits,public.identity_refresh_grants,
                public.identity_authorization_codes,public.identity_browser_sessions,
                public.identity_provider_links,public.identity_oauth_clients,public.identity_accounts;
            DO $$ BEGIN IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='dz_identity_api') THEN
              DROP OWNED BY dz_identity_api; DROP ROLE dz_identity_api; END IF; END $$;
        """)
        await conn.close()
