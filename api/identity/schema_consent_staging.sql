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
