-- Apply to the *Personal MCP goals database* (not the OAuth credentials database).
-- This database is used by the Hatchet worker via DRAGONZPYDER_PERSONAL_MCP_DATABASE_URL.
-- No access tokens, OAuth clients, or provider credentials are stored here.
CREATE TABLE IF NOT EXISTS dz_mcp_goal_selections (
  goal_id text PRIMARY KEY,
  owner_id text NOT NULL,
  selection_hash char(64) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
