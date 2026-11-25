-- Apply to the existing MCP credential database, not the chat DB.
-- A native browser callback stages only encrypted provider code; it cannot
-- grant a connection until the original authenticated device redeems it.
ALTER TABLE dz_mcp_oauth_attempts
    ADD COLUMN IF NOT EXISTS native_challenge text,
    ADD COLUMN IF NOT EXISTS native_callback bytea;
