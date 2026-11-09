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

-- Durable, replay-safe Hatchet goal occurrence ledger.
CREATE TABLE IF NOT EXISTS dragonzpyder_goal_runs (
    run_id uuid PRIMARY KEY,
    goal_id uuid NOT NULL REFERENCES dragonzpyder_goals(goal_id) ON DELETE CASCADE,
    scheduled_for timestamptz NOT NULL,
    status text NOT NULL CHECK (
      status IN ('pending','running','awaiting_authorization',
                 'completed','failed','cancelled')
    ),
    claim_token uuid,
    lease_until timestamptz,
    attempts integer NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 3),
    evidence_sha256 char(64),
    error_code text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(goal_id, scheduled_for)
);
CREATE INDEX IF NOT EXISTS idx_dz_goal_runs_pending
 ON dragonzpyder_goal_runs(status, lease_until)
 WHERE status IN ('pending','running');
