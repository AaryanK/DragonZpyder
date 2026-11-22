-- Apply only after reviewing PostgreSQL roles and backups. No automatic schema creation.
-- A dedicated DB role must have access to these tables, not to identity or chat checkpoints.
CREATE TABLE IF NOT EXISTS dz_mcp_oauth_clients (
  provider_id text PRIMARY KEY,
  issuer text NOT NULL,
  encrypted_client bytea NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dz_mcp_oauth_attempts (
  state_hash char(64) PRIMARY KEY,
  owner_id text NOT NULL,
  session_hash char(64) NOT NULL,
  provider_id text NOT NULL,
  encrypted_flow bytea NOT NULL,
  expires_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS dz_mcp_oauth_attempt_owner_idx
 ON dz_mcp_oauth_attempts(owner_id, expires_at);

CREATE TABLE IF NOT EXISTS dz_mcp_connections (
  id uuid PRIMARY KEY,
  public_alias varchar(31) NOT NULL UNIQUE,
  owner_id text NOT NULL,
  provider_id text NOT NULL,
  display_label varchar(80) NOT NULL,
  issuer text NOT NULL,
  resource text NOT NULL,
  granted_scopes text[] NOT NULL,
  encrypted_tokens bytea,
  access_expires_at timestamptz,
  status text NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'expired', 'revoked')),
  revision bigint NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  revoked_at timestamptz,
  CHECK (status <> 'active' OR encrypted_tokens IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS dz_mcp_connections_owner_idx
 ON dz_mcp_connections(owner_id, provider_id, status);

-- Scheduled account selections belong in the separate Personal goal database.
-- Apply 20261122_personal_mcp_goal_selections.sql to that database, not here.
