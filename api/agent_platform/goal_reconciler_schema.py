"""Schema shared by goal store and Hatchet reconciler, with no import cycles."""
RUN_SCHEMA = """
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
"""
