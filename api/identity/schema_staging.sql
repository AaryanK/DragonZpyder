-- Staging-only, additive schema for a future DragonZpyder-owned identity DB.
-- Never automatically run on production startup. Review and apply using a
-- separately approved, backed-up database migration.
-- Canonical subject is an opaque immutable identifier, not an email.
CREATE TABLE IF NOT EXISTS identity_accounts (
    subject VARCHAR(160) PRIMARY KEY,
    source_operly_user_id VARCHAR(120) NOT NULL UNIQUE,
    status VARCHAR(24) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT identity_account_status CHECK (status IN ('pending', 'active', 'disabled'))
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
-- Import should run in one transaction with strict row-count reconciliation
-- against the validated snapshot and should not issue any access tokens.
