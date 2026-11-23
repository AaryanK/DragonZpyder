-- MANUAL ONE-TIME identity database bootstrap. No automatic API startup DDL.
-- Applies only to a new, dedicated EMPTY database. Approval/backup required.
-- Never includes password hashes, user records or provider client secrets.
BEGIN;
SET LOCAL lock_timeout = '7s';
SET LOCAL statement_timeout = '25s';
SELECT pg_advisory_xact_lock(739110210);
DO $dz$
BEGIN
  IF current_schema() <> 'public' OR EXISTS (
      SELECT 1 FROM pg_catalog.pg_class
      WHERE relnamespace = 'public'::regnamespace
        AND relkind IN ('r','p')
        AND relname LIKE 'identity_%'
  ) THEN
    RAISE EXCEPTION 'Identity schema bootstrap requires an empty public schema';
  END IF;
END
$dz$;

-- FROM schema_staging.sql
-- Phase D: staging-only identity schema. NEVER applied automatically by API startup.
-- Review and run against an isolated restored DB before approving production.
-- A canonical subject is the existing Operly UUID (no identity duplication).
CREATE TABLE IF NOT EXISTS identity_accounts (
    subject VARCHAR(160) PRIMARY KEY,
    source_operly_user_id VARCHAR(120) NOT NULL UNIQUE,
    email VARCHAR(320) NOT NULL UNIQUE,
    password_hash TEXT,
    display_name VARCHAR(200) NOT NULL,
    email_verified_at TIMESTAMPTZ,
    source_active BOOLEAN NOT NULL,
    status VARCHAR(24) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT identity_account_status CHECK (status IN ('pending', 'active', 'disabled')),
    CONSTRAINT identity_account_pending_or_disabled CHECK (status <> 'active')
);
CREATE TABLE IF NOT EXISTS identity_provider_links (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    subject VARCHAR(160) NOT NULL REFERENCES identity_accounts(subject) ON DELETE RESTRICT,
    provider VARCHAR(60) NOT NULL,
    provider_subject VARCHAR(255) NOT NULL,
    source VARCHAR(16) NOT NULL,
    login_eligible BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT identity_link_provider_unique UNIQUE (provider, provider_subject),
    CONSTRAINT identity_link_source CHECK (source IN ('auth', 'external')),
    CONSTRAINT identity_external_not_login CHECK (source <> 'external' OR login_eligible = FALSE)
);
-- All imports use pending accounts only, even if source Operly users are active.
-- The CHECK deliberately forbids activation until an audited auth issuer,
-- revocation and rollback process is ready. Any future activation requires
-- a separately reviewed schema migration; this script is not a login system.

-- FROM schema_native_google_signup.sql
-- Staged identity extension for users who NEVER had Operly accounts.
-- REVIEW / APPLY BY OPERATOR ONLY. Never run on API startup.
-- Existing imported users stay locked pending a separate audited activation.
ALTER TABLE identity_accounts
    ADD COLUMN IF NOT EXISTS identity_origin VARCHAR(32) NOT NULL DEFAULT 'operly_import';
ALTER TABLE identity_accounts
    ALTER COLUMN source_operly_user_id DROP NOT NULL;
ALTER TABLE identity_accounts
    DROP CONSTRAINT IF EXISTS identity_account_pending_or_disabled;
ALTER TABLE identity_accounts
    ADD CONSTRAINT identity_import_not_automatically_active
      CHECK (identity_origin <> 'operly_import' OR status <> 'active');
ALTER TABLE identity_accounts
    ADD CONSTRAINT identity_native_origin_valid
      CHECK (identity_origin IN ('operly_import', 'native_google'));
ALTER TABLE identity_accounts
    ADD CONSTRAINT identity_source_link_consistency
      CHECK ((identity_origin = 'operly_import' AND source_operly_user_id IS NOT NULL)
         OR (identity_origin = 'native_google' AND source_operly_user_id IS NULL));

-- Google subject uniqueness already exists in identity_provider_links.
-- Google/email collision NEVER merges a pre-existing Operly account.
-- A second, independently audited path is required for email/password signup,
-- email verification, forgot-password and account-delete lifecycle.

-- FROM schema_sessions_staging.sql
-- Phase E, staging review only. Separate first-party sessions per site.
-- Identity service cookie stays at DragonZpyder issuer host; Operly does NOT
-- receive this cookie, it maintains a separate authenticated client session.
CREATE TABLE IF NOT EXISTS identity_browser_sessions (
    session_hash CHAR(64) PRIMARY KEY,
    csrf_hash CHAR(64) NOT NULL,
    subject VARCHAR(160) NOT NULL REFERENCES identity_accounts(subject) ON DELETE RESTRICT,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_identity_browser_sessions_subject
    ON identity_browser_sessions(subject);
CREATE INDEX IF NOT EXISTS ix_identity_browser_sessions_expiration
    ON identity_browser_sessions(expires_at);

-- FROM schema_login_staging.sql
-- Phase G, isolated staging migration only; never auto-apply on API startup.
-- HMAC(email) avoids plaintext login identifiers in throttling records.
CREATE TABLE IF NOT EXISTS identity_login_rate_limits (
    identity_digest CHAR(64) PRIMARY KEY,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    window_started_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT identity_login_attempts_positive CHECK (attempt_count >= 0)
);
CREATE INDEX IF NOT EXISTS ix_identity_login_rate_window ON identity_login_rate_limits(window_started_at);
-- Purge expired windows periodically from a privileged maintenance process.

-- FROM schema_oauth_staging.sql
-- Phase E: review-only OAuth grant schema; DO NOT run automatically.
-- Additional prerequisites: audited auth sessions, account activation policy,
-- approved OAuth clients and production-grade key rotation.
CREATE TABLE IF NOT EXISTS identity_oauth_clients (
    client_id VARCHAR(100) PRIMARY KEY,
    redirect_uri TEXT NOT NULL,
    audience VARCHAR(150) NOT NULL,
    allowed_scope TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT oauth_client_redirect CHECK (length(redirect_uri) BETWEEN 12 AND 2048)
);
CREATE TABLE IF NOT EXISTS identity_authorization_codes (
    code_hash CHAR(64) PRIMARY KEY,
    subject VARCHAR(160) NOT NULL REFERENCES identity_accounts(subject) ON DELETE RESTRICT,
    client_id VARCHAR(100) NOT NULL REFERENCES identity_oauth_clients(client_id) ON DELETE RESTRICT,
    redirect_uri TEXT NOT NULL,
    pkce_s256 VARCHAR(43) NOT NULL,
    nonce VARCHAR(128),
    scope TEXT NOT NULL,
    audience VARCHAR(150) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_identity_auth_codes_expiry
    ON identity_authorization_codes(expires_at);
CREATE TABLE IF NOT EXISTS identity_refresh_grants (
    refresh_hash CHAR(64) PRIMARY KEY,
    subject VARCHAR(160) NOT NULL REFERENCES identity_accounts(subject) ON DELETE RESTRICT,
    client_id VARCHAR(100) NOT NULL REFERENCES identity_oauth_clients(client_id) ON DELETE RESTRICT,
    family_id VARCHAR(64) NOT NULL,
    scope TEXT NOT NULL,
    audience VARCHAR(150) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_identity_refresh_family
    ON identity_refresh_grants(family_id);
-- No client is enabled or account activated by this schema.

-- FROM schema_provider_challenge_staging.sql
-- Phase H staging-only login proof challenges; do not apply at API startup.
-- Challenge states are opaque, single use and browser bound.
CREATE TABLE IF NOT EXISTS identity_provider_challenges (
    state_hash CHAR(64) PRIMARY KEY,
    binding_hash CHAR(64) NOT NULL,
    provider VARCHAR(20) NOT NULL,
    nonce VARCHAR(128),
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT identity_provider_challenge_name CHECK (provider IN ('google', 'discord'))
);
CREATE INDEX IF NOT EXISTS ix_identity_provider_challenges_expiry
    ON identity_provider_challenges(expires_at);

-- FROM schema_consent_staging.sql
-- Dedicated operator-installed identity interaction table. No production auto-migration.
CREATE TABLE IF NOT EXISTS identity_authorization_interactions (
  ticket_hash CHAR(64) PRIMARY KEY,
  subject VARCHAR(160) NOT NULL REFERENCES identity_accounts(subject) ON DELETE RESTRICT,
  session_hash CHAR(64) NOT NULL REFERENCES identity_browser_sessions(session_hash) ON DELETE CASCADE,
  request_sha256 CHAR(64) NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  consumed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_identity_interactions_expiry
  ON identity_authorization_interactions(expires_at);
CREATE INDEX IF NOT EXISTS ix_identity_interactions_session
  ON identity_authorization_interactions(session_hash);

-- FROM schema_first_party_clients_staging.sql
-- OPERATOR-ONLY exact OAuth client registration, not an automatic startup migration.
-- Requires the separate dedicated identity DB and schema_oauth_staging.sql.
-- Adds neither an account nor an enabled client.
SELECT pg_advisory_xact_lock(739110212);
DO $$
BEGIN
    IF EXISTS (
      SELECT 1 FROM identity_oauth_clients
      WHERE (client_id = 'operly-web' AND (
         redirect_uri <> 'https://operly.dragonzpyder.xyz/api/auth/dragonzpyder/callback'
         OR audience <> 'operly-api'
         OR allowed_scope <> 'openid operly:access'))
      OR (client_id = 'dragonzpyder-web' AND (
         redirect_uri <> 'https://dragonzpyder.xyz/api/auth/dragonzpyder/web/callback'
         OR audience <> 'operly-api'
         OR allowed_scope <> 'openid operly:access'))
    ) THEN
      RAISE EXCEPTION 'Existing first-party client configuration differs from reviewed registration';
    END IF;
END $$;
INSERT INTO identity_oauth_clients
  (client_id, redirect_uri, audience, allowed_scope, enabled)
VALUES
  ('operly-web',
   'https://operly.dragonzpyder.xyz/api/auth/dragonzpyder/callback',
   'operly-api', 'openid operly:access', FALSE),
  ('dragonzpyder-web',
   'https://dragonzpyder.xyz/api/auth/dragonzpyder/web/callback',
   'operly-api', 'openid operly:access', FALSE)
ON CONFLICT (client_id) DO NOTHING;

-- All imported subjects remain PENDING; both OAuth clients are disabled.
DO $dz$
BEGIN
  IF (SELECT count(*) FROM identity_accounts) <> 0 OR
     EXISTS (SELECT 1 FROM identity_oauth_clients WHERE enabled) THEN
    RAISE EXCEPTION 'Identity bootstrap accidentally enabled or imported accounts';
  END IF;
END
$dz$;
COMMIT;
