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
