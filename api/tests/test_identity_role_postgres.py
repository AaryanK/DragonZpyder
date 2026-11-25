"""Disposable real-PG role and RLS acceptance. Run after schema bootstrap in isolated CI only."""
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit
import asyncpg
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

@pytest.mark.asyncio
async def test_least_privileged_identity_role_disposable_pg():
    dsn = os.getenv("DRAGONZPYDER_IDENTITY_TEST_DSN", "")
    if not dsn:
        pytest.skip("No disposable identity PostgreSQL")
    if urlsplit(dsn).path != "/identity_test":
        raise RuntimeError("Refuse non-disposable database")
    conn = await asyncpg.connect(dsn)
    base = Path(__file__).resolve().parents[1] / "identity"
    # Roll back the entire fixture, including global role and policies.
    tx = conn.transaction()
    await tx.start()
    try:
        for sql in ("schema_bootstrap_manual.sql", "schema_role_manual.sql"):
            text = (base / sql).read_text("utf-8")
            # Remove the outer transaction, not nested DO block statements.
            text = text.replace("BEGIN;\nSET LOCAL", "SET LOCAL", 1).removesuffix("COMMIT;\n")
            if sql == "schema_bootstrap_manual.sql" and await conn.fetchval(
                "SELECT to_regclass('public.identity_accounts') IS NOT NULL"
            ):
                # The preceding disposable bootstrap test already installed
                # the reviewed schema. Never DROP a schema to run this test.
                continue
            await conn.execute(text)
        await conn.execute("""INSERT INTO identity_accounts
            (subject,source_operly_user_id,email,display_name,source_active)
            VALUES ('imported','imported','imported@example.test','Imported',TRUE)""")
        await conn.execute("SET LOCAL ROLE dz_identity_api")
        assert not await conn.fetchval("SELECT has_column_privilege(current_user,'public.identity_accounts','status','UPDATE')")
        assert not await conn.fetchval("SELECT has_any_column_privilege(current_user,'public.identity_oauth_clients','UPDATE')")
        async with conn.transaction():
            await conn.execute("""INSERT INTO public.identity_accounts
                (subject,source_operly_user_id,identity_origin,email,password_hash,display_name,
                 email_verified_at,source_active,status)
                VALUES ('native',NULL,'native_google','native@example.test',NULL,'Native',now(),TRUE,'active')""")
            await conn.execute("""INSERT INTO public.identity_provider_links
                (subject,provider,provider_subject,source,login_eligible)
                VALUES ('native','google','google-native','auth',TRUE)""")
            await conn.execute("UPDATE public.identity_accounts SET display_name='Changed' WHERE subject='native'")
        for query in (
            "UPDATE public.identity_accounts SET status='active' WHERE subject='imported'",
            "UPDATE public.identity_oauth_clients SET enabled=TRUE",
            "DELETE FROM public.identity_accounts WHERE subject='imported'",
            """INSERT INTO public.identity_provider_links(subject,provider,provider_subject,source,login_eligible)
               VALUES ('imported','google','malicious-link','auth',TRUE)""",
            """INSERT INTO public.identity_accounts(subject,source_operly_user_id,identity_origin,email,password_hash,display_name,email_verified_at,source_active,status)
               VALUES ('fake','fake','operly_import','fake@example.test',NULL,'Fake',now(),TRUE,'pending')""",
        ):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                async with conn.transaction():
                    await conn.execute(query)
    finally:
        await tx.rollback()
        await conn.close()
