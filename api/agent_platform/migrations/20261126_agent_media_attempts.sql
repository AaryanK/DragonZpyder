CREATE TABLE IF NOT EXISTS dz_agent_media_attempts (
 owner_id text NOT NULL, run_id uuid NOT NULL, operation_id uuid PRIMARY KEY,
 kind text NOT NULL CHECK(kind IN ('vision','image','speech','transcribe')),
 request_sha256 char(64) NOT NULL,
 state text NOT NULL CHECK(state IN ('reserved','returned')),
 gateway_request_id text, trace_id text, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS dz_agent_media_attempts_owner ON dz_agent_media_attempts(owner_id,created_at);
