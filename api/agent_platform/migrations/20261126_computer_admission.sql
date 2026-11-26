-- Apply explicitly with the Personal computer rollout.
CREATE TABLE IF NOT EXISTS dz_computer_allocations (
    run_id uuid PRIMARY KEY,
    owner_id text NOT NULL,
    client_session_id text NOT NULL,
    quota_day date NOT NULL DEFAULT (now() AT TIME ZONE 'UTC')::date,
    held_usd numeric(20,10) NOT NULL CHECK (held_usd>0),
    state text NOT NULL CHECK (state IN ('reserved','active','uncertain','destroyed')),
    sandbox_id text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(owner_id,client_session_id)
);
CREATE INDEX IF NOT EXISTS dz_computer_allocations_owner_day
  ON dz_computer_allocations(owner_id,quota_day);
CREATE INDEX IF NOT EXISTS dz_computer_allocations_active
  ON dz_computer_allocations(state) WHERE state IN ('reserved','active','uncertain');
