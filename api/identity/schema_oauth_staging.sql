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
