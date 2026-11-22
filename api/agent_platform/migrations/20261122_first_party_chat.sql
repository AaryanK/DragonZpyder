-- Apply manually to the DragonZpyder AGENT checkpoint database using a
-- dedicated migration role BEFORE DRAGONZPYDER_FIRST_PARTY_CHAT_ENABLED=1.
-- This table never stores provider credentials, Operly leases or tool grants.
CREATE TABLE IF NOT EXISTS dz_first_party_conversations (
    id uuid PRIMARY KEY,
    owner_id text NOT NULL CHECK (length(owner_id) BETWEEN 1 AND 160),
    title text NOT NULL CHECK (length(title) BETWEEN 1 AND 80),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS dz_first_party_conversations_owner_updated_idx
    ON dz_first_party_conversations(owner_id, updated_at DESC);

-- Application queries always bind owner_id derived from the live first-party
-- identity session. Grant no public or anonymous access to this database.
