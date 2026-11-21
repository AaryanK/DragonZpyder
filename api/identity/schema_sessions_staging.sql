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
