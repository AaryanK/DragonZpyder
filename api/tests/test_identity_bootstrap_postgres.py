"""Real disposable PostgreSQL acceptance for empty identity bootstrap.

NEVER accepts production DSN, never uses Operly's source data.
"""
import os
from pathlib import Path
from urllib.parse import urlsplit
import asyncpg
import pytest

BASE = Path(__file__).resolve().parents[1] / "identity"
SQL = (BASE / "schema_bootstrap_manual.sql").read_text("utf-8")


@pytest.mark.asyncio
async def test_identity_bootstrap_on_empty_disposable_postgres_only():
    dsn = os.getenv("DRAGONZPYDER_IDENTITY_TEST_DSN", "")
    if not dsn:
        pytest.skip("No dedicated disposable identity_test PostgreSQL")
    if urlsplit(dsn).path != "/identity_test":
        raise RuntimeError("Never run bootstrap test outside identity_test")
    conn = await asyncpg.connect(dsn)
    try:
        assert await conn.fetchval(
            """SELECT count(*) FROM pg_tables
               WHERE schemaname='public' AND tablename LIKE 'identity_%'""") == 0
        await conn.execute(SQL)
        expected = {
            "identity_accounts", "identity_provider_links",
            "identity_browser_sessions", "identity_oauth_clients",
            "identity_authorization_codes", "identity_refresh_grants",
            "identity_provider_challenges", "identity_authorization_interactions",
            "identity_login_rate_limits",
        }
        tables = set(await conn.fetch(
            """SELECT tablename FROM pg_tables
               WHERE schemaname='public' AND tablename LIKE 'identity_%'"""))
        assert expected.issubset({row["tablename"] for row in tables})
        assert await conn.fetchval(
            "SELECT count(*) FROM identity_oauth_clients WHERE enabled") == 0
        assert await conn.fetchval("SELECT count(*) FROM identity_accounts") == 0

        # An imported Workspace ID remains protected from automatic activation.
        await conn.execute(
            """INSERT INTO identity_accounts
              (subject, source_operly_user_id, email, display_name,
               source_active, status)
               VALUES ('imported-1', 'operly-uuid-1', 'one@example.test',
                       'Imported', TRUE, 'pending')""")
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute(
                "UPDATE identity_accounts SET status='active' WHERE subject='imported-1'")
        # Native Google registration can independently create an active user.
        await conn.execute(
            """INSERT INTO identity_accounts
              (subject, source_operly_user_id, identity_origin, email,
               display_name, source_active, status)
               VALUES ('native-2', NULL, 'native_google', 'two@example.test',
                       'Native', TRUE, 'active')""")
        with pytest.raises(asyncpg.UniqueViolationError):
            await conn.execute(
                """INSERT INTO identity_accounts
                   (subject,source_operly_user_id,identity_origin,email,
                    display_name,source_active,status)
                   VALUES ('fake-3',NULL,'native_google','two@example.test',
                           'Duplicate',TRUE,'active')""")
        assert await conn.fetchval(
            "SELECT status FROM identity_accounts WHERE subject='imported-1'"
        ) == "pending"
        assert await conn.fetchval(
            "SELECT count(*) FROM identity_accounts WHERE status='active'"
        ) == 1
        with pytest.raises(asyncpg.RaiseError):
            await conn.execute(SQL)
    finally:
        await conn.close()
