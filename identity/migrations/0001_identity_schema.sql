-- Identity database schema proposal; do not run against Operly production.
CREATE TABLE IF NOT EXISTS dz_humans (
  id UUID PRIMARY KEY,
  email_normalized TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL,
  email_verified_at TIMESTAMPTZ,
  password_hash TEXT,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS dz_external_identities (
  id UUID PRIMARY KEY,
  human_id UUID NOT NULL REFERENCES dz_humans(id) ON DELETE CASCADE,
  provider TEXT NOT NULL,
  provider_subject TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT dz_external_subject UNIQUE(provider,provider_subject),
  CONSTRAINT dz_human_one_provider UNIQUE(human_id,provider)
);
CREATE TABLE IF NOT EXISTS dz_operly_subject_mapping (
  operly_user_id UUID PRIMARY KEY,
  human_id UUID NOT NULL UNIQUE REFERENCES dz_humans(id) ON DELETE RESTRICT,
  link_method TEXT NOT NULL CHECK(link_method IN ('verified_migration','explicit_account_link')),
  verified_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- Sessions, authorization codes, refresh tokens, key rotation and MFA need
-- an established identity server's own schema and migration system.
