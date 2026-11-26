-- Apply explicitly before enabling the shared artifact service.
CREATE TABLE IF NOT EXISTS dz_agent_artifacts (
    owner_id text NOT NULL,
    id uuid NOT NULL,
    filename text NOT NULL,
    content_type text NOT NULL,
    byte_count integer NOT NULL CHECK (byte_count BETWEEN 1 AND 10485760),
    sha256 text NOT NULL,
    nonce bytea NOT NULL CHECK (octet_length(nonce)=12),
    ciphertext bytea NOT NULL,
    direction text NOT NULL CHECK (direction IN ('upload','generated')),
    run_id uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(owner_id,id)
);
CREATE INDEX IF NOT EXISTS dz_agent_artifacts_run_idx ON dz_agent_artifacts(owner_id,run_id);
