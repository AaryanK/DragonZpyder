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
