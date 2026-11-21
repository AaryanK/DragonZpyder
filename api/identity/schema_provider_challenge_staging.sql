-- Phase H staging-only login proof challenges; do not apply at API startup.
-- Challenge states are opaque, single use and browser bound.
CREATE TABLE IF NOT EXISTS identity_provider_challenges (
    state_hash CHAR(64) PRIMARY KEY,
    binding_hash CHAR(64) NOT NULL,
    provider VARCHAR(20) NOT NULL,
    nonce VARCHAR(128),
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT identity_provider_challenge_name CHECK (provider IN ('google', 'discord'))
);
CREATE INDEX IF NOT EXISTS ix_identity_provider_challenges_expiry
    ON identity_provider_challenges(expires_at);
