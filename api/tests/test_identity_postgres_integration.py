"""Real, isolated PostgreSQL proof of code consumption and refresh replay fencing.

Only runs when the DSN points to a disposable database named identity_test.
Creates and removes its own schema. Never reads or alters Operly production.
"""
import asyncio
import json
import os
import sys
import uuid
from pathlib import Path
from urllib.parse import urlsplit

import asyncpg
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from identity.grants import authorize_code, OAuthGrantDenied
from identity.exchange import exchange_code, exchange_refresh
from identity.tokens import SigningIdentity, pkce_challenge

BASE = Path(__file__).resolve().parents[1] / "identity"
REDIRECT = "https://operly.dragonzpyder.xyz/auth/callback"
VERIFIER = "v" * 54


@pytest.mark.asyncio
async def test_real_postgres_code_exchange_and_refresh_replay(monkeypatch):
    dsn = os.getenv("DRAGONZPYDER_IDENTITY_TEST_DSN", "")
    if not dsn:
        pytest.skip("No explicitly isolated identity test PostgreSQL")
    if urlsplit(dsn).path != "/identity_test":
        raise RuntimeError("Refusing to run identity integration tests outside identity_test DB")
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_GRANT_HASH_KEY", "ci-only-opaque-grant-key-material-" + "x" * 32)

    conn = await asyncpg.connect(dsn)
    other = await asyncpg.connect(dsn)
    name = "idcheck_" + uuid.uuid4().hex
    try:
        await conn.execute(f"CREATE SCHEMA {name}")
        await conn.execute(f"SET search_path TO {name}")
        await other.execute(f"SET search_path TO {name}")
        for file in ("schema_staging.sql", "schema_oauth_staging.sql"):
            await conn.execute((BASE / file).read_text(encoding="utf-8"))
        await conn.execute(
            """INSERT INTO identity_accounts
               (subject,source_operly_user_id,email,display_name,source_active,status)
               VALUES ($1,$1,'person@example.test','Test Account',TRUE,'pending')""",
            "same-operly-user-id",
        )
        await conn.execute(
            """INSERT INTO identity_oauth_clients
               (client_id,redirect_uri,audience,allowed_scope,enabled)
               VALUES ('operly-web',$1,'operly-api','openid offline_access operly:access',TRUE)""",
            REDIRECT,
        )
        with pytest.raises(OAuthGrantDenied):
            await authorize_code(
                conn, authenticated_subject="same-operly-user-id",
                client_id="operly-web", redirect_uri=REDIRECT,
                scope="openid offline_access operly:access",
                pkce_s256=pkce_challenge(VERIFIER), nonce="n" * 40,
            )
        # The staging DDL has a hard account-activation fence. This DROP is
        # strictly inside the disposable CI-only schema, never a migration.
        await conn.execute(
            "ALTER TABLE identity_accounts DROP CONSTRAINT identity_account_pending_or_disabled"
        )
        await conn.execute(
            "UPDATE identity_accounts SET status='active' WHERE subject='same-operly-user-id'"
        )

        signer_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
        pem = signer_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                       serialization.NoEncryption())
        signer = SigningIdentity("https://api.dragonzpyder.xyz", "ci-synthetic", pem)
        issued = await authorize_code(
            conn, authenticated_subject="same-operly-user-id",
            client_id="operly-web", redirect_uri=REDIRECT,
            scope="openid offline_access operly:access",
            pkce_s256=pkce_challenge(VERIFIER), nonce="n" * 40,
        )
        response = await exchange_code(
            conn, signer, code=issued.code,
            client_id="operly-web", redirect_uri=REDIRECT, code_verifier=VERIFIER,
        )
        pub = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(signer.jwk()))
        claims = jwt.decode(response["id_token"], pub, algorithms=["RS256"],
                            audience="operly-web", issuer=signer.issuer)
        assert claims["sub"] == "same-operly-user-id"
        assert claims["nonce"] == "n" * 40
        assert response["refresh_token"]
        assert await conn.fetchval(
            "SELECT count(*) FROM identity_authorization_codes WHERE consumed_at IS NOT NULL"
        ) == 1
        with pytest.raises(OAuthGrantDenied):
            await exchange_code(
                conn, signer, code=issued.code, client_id="operly-web",
                redirect_uri=REDIRECT, code_verifier=VERIFIER,
            )

        old_refresh = response["refresh_token"]
        results = await asyncio.gather(
            exchange_refresh(conn, signer, refresh_token=old_refresh,
                             client_id="operly-web", redirect_uri=REDIRECT),
            exchange_refresh(other, signer, refresh_token=old_refresh,
                             client_id="operly-web", redirect_uri=REDIRECT),
            return_exceptions=True,
        )
        # At most one rotation succeeds; reuse must commit a family-wide revoke.
        successes = [r for r in results if isinstance(r, dict)]
        failures = [r for r in results if isinstance(r, OAuthGrantDenied)]
        assert len(successes) == 1 and len(failures) == 1, results
        assert await conn.fetchval(
            "SELECT count(*) FROM identity_refresh_grants WHERE revoked_at IS NULL"
        ) == 0
        with pytest.raises(OAuthGrantDenied):
            await exchange_refresh(
                conn, signer, refresh_token=successes[0]["refresh_token"],
                client_id="operly-web", redirect_uri=REDIRECT,
            )
    finally:
        await other.close()
        await conn.execute(f"DROP SCHEMA IF EXISTS {name} CASCADE")
        await conn.close()
