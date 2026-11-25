-- Run with the existing agent database migration role before enabling request IDs.
-- An accepted request is never implicitly retried, even after worker loss.
CREATE TABLE IF NOT EXISTS dz_first_party_chat_requests (
    owner_id text NOT NULL CHECK (length(owner_id) BETWEEN 1 AND 160),
    request_id uuid NOT NULL,
    fingerprint char(64) NOT NULL,
    conversation_id uuid NOT NULL,
    status text NOT NULL CHECK (status IN ('accepted','completed','uncertain')),
    response jsonb,
    cancel_requested boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (owner_id, request_id),
    CHECK ((status = 'completed') = (response IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS dz_first_party_chat_requests_owner_updated
    ON dz_first_party_chat_requests(owner_id, updated_at DESC);
-- Retain IDs for as long as client retry remains possible. Do not delete
-- uncertain entries or reuse a request ID to execute a second time.

ALTER TABLE dz_first_party_chat_requests ADD COLUMN IF NOT EXISTS cancel_requested boolean NOT NULL DEFAULT false;
