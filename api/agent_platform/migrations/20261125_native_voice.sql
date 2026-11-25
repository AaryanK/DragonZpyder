-- Existing agent database; no provider keys or audio are persisted here.
CREATE TABLE IF NOT EXISTS dz_native_voice_sessions (
    owner_id text NOT NULL,
    session_id uuid NOT NULL,
    provider_call_id text,
    state text NOT NULL CHECK(state IN ('starting','active','closed','unknown')),
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(owner_id, session_id)
);
CREATE INDEX IF NOT EXISTS dz_native_voice_expiry
    ON dz_native_voice_sessions(expires_at) WHERE state='active';
