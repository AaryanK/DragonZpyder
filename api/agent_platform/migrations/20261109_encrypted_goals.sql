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

-- Atomic event watcher + inbox + durable wakeup journal.
CREATE TABLE IF NOT EXISTS dragonzpyder_event_watches (
    monitor_id varchar(64) PRIMARY KEY,
    query text NOT NULL,
    provider text NOT NULL CHECK (provider IN ('wikipedia')),
    query_sha256 char(64) NOT NULL,
    last_sources jsonb NOT NULL DEFAULT '[]'::jsonb,
    last_fingerprint char(64),
    checked_at timestamptz,
    next_check_at timestamptz NOT NULL,
    check_interval_seconds integer NOT NULL
      CHECK (check_interval_seconds BETWEEN 300 AND 86400),
    checks bigint NOT NULL DEFAULT 0,
    active boolean NOT NULL DEFAULT true
);
CREATE INDEX IF NOT EXISTS idx_dz_event_watches_due
 ON dragonzpyder_event_watches(next_check_at)
 WHERE active;
CREATE TABLE IF NOT EXISTS dragonzpyder_event_waits (
    wait_id uuid PRIMARY KEY,
    source_app text NOT NULL,
    principal_hash char(64) NOT NULL,
    request_id uuid NOT NULL,
    monitor_id varchar(64) NOT NULL
       REFERENCES dragonzpyder_event_watches(monitor_id),
    status text NOT NULL CHECK (status IN ('armed','delivered','cancelled')),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(source_app, principal_hash, request_id)
);
CREATE TABLE IF NOT EXISTS dragonzpyder_event_inbox (
    event_id uuid PRIMARY KEY,
    monitor_id varchar(64) NOT NULL
       REFERENCES dragonzpyder_event_watches(monitor_id),
    fingerprint char(64) NOT NULL,
    observed_at timestamptz NOT NULL,
    UNIQUE(monitor_id, fingerprint)
);
CREATE TABLE IF NOT EXISTS dragonzpyder_event_wakes (
    wake_id uuid PRIMARY KEY,
    wait_id uuid NOT NULL
        REFERENCES dragonzpyder_event_waits(wait_id),
    event_id uuid NOT NULL
        REFERENCES dragonzpyder_event_inbox(event_id),
    status text NOT NULL CHECK (status IN
       ('pending','running','completed','awaiting_authorization',
        'cancelled','failed')),
    claim_token uuid,
    lease_until timestamptz,
    attempts integer NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 3),
    evidence_sha256 char(64),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(wait_id, event_id)
);
CREATE INDEX IF NOT EXISTS idx_dz_event_wakes_pending
 ON dragonzpyder_event_wakes(status,lease_until)
 WHERE status IN ('pending','running');

-- Durable owner-scoped Web harness tasks and operational events.
CREATE TABLE IF NOT EXISTS dragonzpyder_ui_tasks (
    task_id uuid PRIMARY KEY,
    owner_hash char(64) NOT NULL,
    request_id uuid NOT NULL,
    kind text NOT NULL CHECK(kind IN ('probe','agent')),
    prompt_sha256 char(64) NOT NULL,
    prompt_ciphertext bytea NOT NULL,
    result_ciphertext bytea,
    status text NOT NULL CHECK(status IN
       ('queued','running','completed','incomplete','failed','cancelled')),
    claim_token uuid,
    lease_until timestamptz,
    attempts integer NOT NULL DEFAULT 0 CHECK(attempts BETWEEN 0 AND 2),
    objective_verified boolean NOT NULL DEFAULT false,
    trace_id varchar(64),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(owner_hash,request_id)
);
CREATE INDEX IF NOT EXISTS idx_dz_ui_tasks_owner
  ON dragonzpyder_ui_tasks(owner_hash,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_dz_ui_tasks_status
  ON dragonzpyder_ui_tasks(status,updated_at DESC);
CREATE TABLE IF NOT EXISTS dragonzpyder_ui_task_events (
    event_id bigserial PRIMARY KEY,
    task_id uuid NOT NULL REFERENCES dragonzpyder_ui_tasks(task_id)
       ON DELETE CASCADE,
    kind varchar(32) NOT NULL,
    message varchar(180) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_dz_ui_events_task
  ON dragonzpyder_ui_task_events(task_id,event_id);
