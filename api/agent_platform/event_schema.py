"""Outbox-backed event waits, deduplicated web monitor events and wake receipts.

Must share the SAME PostgreSQL database and transaction as web snapshot
updates. A failed worker can retry a pending wake after its lease expires.
"""
EVENT_SCHEMA = """
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
"""
