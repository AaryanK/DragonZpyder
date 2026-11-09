-- DragonZpyder-owned encrypted durable goals. Apply to a dedicated Postgres
-- database before enabling DRAGONZPYDER_GOAL_STORE_ENABLED.
-- No workflow actions execute merely because a goal record is registered.
CREATE TABLE IF NOT EXISTS dragonzpyder_goals (
    goal_id uuid PRIMARY KEY,
    source_app text NOT NULL,
    principal_hash char(64) NOT NULL,
    request_id uuid NOT NULL,
    payload_sha256 char(64) NOT NULL,
    goal_ciphertext bytea NOT NULL,
    schedule_json jsonb,
    next_run_at timestamptz,
    status text NOT NULL DEFAULT 'registered'
      CHECK (status IN ('registered','awaiting_authorization',
                        'paused','cancelled','completed')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(source_app, principal_hash, request_id)
);
CREATE INDEX IF NOT EXISTS idx_dz_goals_due
 ON dragonzpyder_goals (next_run_at)
 WHERE status = 'registered';
