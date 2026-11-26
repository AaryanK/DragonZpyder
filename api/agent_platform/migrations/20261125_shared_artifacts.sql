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

-- Existing rows remain readable; new object-backed bytes use a durable
-- pending reservation and only become visible after independent readback.
ALTER TABLE dz_agent_artifacts ALTER COLUMN ciphertext DROP NOT NULL;
ALTER TABLE dz_agent_artifacts ADD COLUMN IF NOT EXISTS object_key text;
ALTER TABLE dz_agent_artifacts ADD COLUMN IF NOT EXISTS storage_state text NOT NULL DEFAULT 'ready';
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname='dz_agent_artifacts_storage_contract'
                  AND conrelid='dz_agent_artifacts'::regclass) THEN
    ALTER TABLE dz_agent_artifacts DROP CONSTRAINT dz_agent_artifacts_storage_contract;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='dz_agent_artifacts_storage_contract_v2'
                  AND conrelid='dz_agent_artifacts'::regclass) THEN
    ALTER TABLE dz_agent_artifacts ADD CONSTRAINT dz_agent_artifacts_storage_contract_v2
      CHECK (storage_state IN ('pending','ready','deleting','deleted') AND
             ((object_key IS NULL AND ciphertext IS NOT NULL AND storage_state='ready') OR
              (object_key IS NOT NULL AND ciphertext IS NULL)));
  END IF;
END $$;
CREATE UNIQUE INDEX IF NOT EXISTS dz_agent_artifacts_object_key_idx
  ON dz_agent_artifacts(object_key) WHERE object_key IS NOT NULL;
