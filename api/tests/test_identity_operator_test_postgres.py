"""Real PostgreSQL proof: operator tests use ordinary auth and expire closed."""
import os
import secrets
import sys
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import asyncpg
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DSN = os.getenv("DRAGONZPYDER_IDENTITY_TEST_DSN", "")


@pytest.mark.asyncio
@pytest.mark.skipif(not DSN, reason="No disposable identity_test PostgreSQL")
async def test_operator_principal_expiry_and_normal_password_auth(monkeypatch):
    if urlsplit(DSN).path != "/identity_test":
        raise RuntimeError("Refuse non-disposable database")
    from identity.passwords import hash_password
    from identity.password_login import password_login, LoginDenied
    from identity.sessions import resolve_browser_session, SessionDenied
    from identity.http_bridge import _restricted_identity_role
    from fastapi import HTTPException

    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_GRANT_HASH_KEY", "test-only-pepper-" + "x" * 48)
    conn = await asyncpg.connect(DSN)
    tx = conn.transaction()
    await tx.start()
    try:
        assert await conn.fetchval("SELECT to_regclass('public.identity_accounts') IS NULL")
        for name in ("schema_bootstrap_manual.sql", "schema_role_manual.sql",
                     "schema_import_activation_review.sql", "schema_operator_test_manual.sql"):
            sql = (ROOT / "identity" / name).read_text()
            await conn.execute(sql.replace("BEGIN;\nSET LOCAL", "SET LOCAL", 1).removesuffix("COMMIT;\n"))
        subject = uuid4()
        email = f"acceptance-{subject}@dragonzpyder.invalid"
        password = secrets.token_urlsafe(36)
        hashed = hash_password(password)
        expiry = await conn.fetchval("SELECT provision_operator_test_identity($1,$2,60)", subject, hashed)
        assert expiry is not None
        assert await conn.fetchval("SELECT count(*) FROM identity_provider_links") == 0
        for minutes in (0, 481):
            with pytest.raises(asyncpg.RaiseError):
                async with conn.transaction():
                    await conn.execute("SELECT provision_operator_test_identity($1,$2,$3)", uuid4(), hashed, minutes)
        with pytest.raises(asyncpg.UniqueViolationError):
            async with conn.transaction():
                await conn.execute("SELECT provision_operator_test_identity($1,$2,60)", subject, hashed)
        await conn.execute("INSERT INTO identity_accounts(subject,source_operly_user_id,email,display_name,source_active) VALUES('pending','pending','pending@example.test','Pending',true)")
        with pytest.raises(asyncpg.CheckViolationError):
            async with conn.transaction():
                await conn.execute("UPDATE identity_accounts SET status='active' WHERE subject='pending'")

        await conn.execute("SET SESSION AUTHORIZATION dz_identity_api")
        try:
            await _restricted_identity_role(conn)
            with pytest.raises(LoginDenied):
                await password_login(conn, email=email, password=secrets.token_urlsafe(36))
            session = await password_login(conn, email=email, password=password)
            assert await resolve_browser_session(conn, secret=session.secret, csrf=session.csrf, require_csrf=True) == str(subject)
            with pytest.raises(SessionDenied):
                await resolve_browser_session(conn, secret=session.secret, csrf="x" * 40, require_csrf=True)
            for sql, args in (
                ("SELECT provision_operator_test_identity($1,$2,60)", (uuid4(), hashed)),
                ("UPDATE identity_accounts SET operator_test_expires_at=now()+interval '8 hours' WHERE subject=$1", (str(subject),)),
                ("UPDATE identity_accounts SET identity_origin='native_google' WHERE subject=$1", (str(subject),)),
                ("INSERT INTO identity_provider_links(subject,provider,provider_subject,source,login_eligible) VALUES($1,'google','forged','auth',true)", (str(subject),)),
            ):
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    async with conn.transaction():
                        await conn.execute(sql, *args)
        finally:
            await conn.execute("RESET SESSION AUTHORIZATION")

        await conn.execute("GRANT UPDATE(operator_test_expires_at) ON identity_accounts TO dz_identity_api")
        await conn.execute("SET SESSION AUTHORIZATION dz_identity_api")
        try:
            with pytest.raises(HTTPException):
                await _restricted_identity_role(conn)
        finally:
            await conn.execute("RESET SESSION AUTHORIZATION")
        await conn.execute("REVOKE UPDATE(operator_test_expires_at) ON identity_accounts FROM dz_identity_api")
        # Expiry affects already-issued cookies, with no API restart or cron.
        await conn.execute("UPDATE identity_accounts SET created_at=now()-interval '2 hours',operator_test_expires_at=now()-interval '1 hour' WHERE subject=$1", str(subject))
        await conn.execute("SET SESSION AUTHORIZATION dz_identity_api")
        try:
            with pytest.raises(SessionDenied):
                await resolve_browser_session(conn, secret=session.secret)
            with pytest.raises(LoginDenied):
                await password_login(conn, email=email, password=password)
        finally:
            await conn.execute("RESET SESSION AUTHORIZATION")
    finally:
        await tx.rollback()
        await conn.close()
