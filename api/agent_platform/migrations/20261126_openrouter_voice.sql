-- Apply after modular voice and native chat request ledger migrations.
CREATE TABLE IF NOT EXISTS dz_openrouter_voice_turns (
    owner_id text NOT NULL, session_id uuid NOT NULL, event_id uuid NOT NULL,
    request_id uuid NOT NULL, audio_sha256 text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(owner_id,session_id,event_id),
    FOREIGN KEY(owner_id,session_id) REFERENCES dz_native_voice_sessions(owner_id,session_id)
);
CREATE TABLE IF NOT EXISTS dz_openrouter_voice_speech (
    owner_id text NOT NULL, session_id uuid NOT NULL,event_id uuid NOT NULL,
    segment integer NOT NULL CHECK(segment BETWEEN 0 AND 3),
    created_at timestamptz NOT NULL DEFAULT now(),PRIMARY KEY(owner_id,session_id,event_id,segment),
    FOREIGN KEY(owner_id,session_id,event_id) REFERENCES dz_openrouter_voice_turns(owner_id,session_id,event_id)
);

ALTER TABLE dz_native_voice_sessions ADD COLUMN IF NOT EXISTS source_channel text NOT NULL DEFAULT 'browser';
ALTER TABLE dz_native_voice_sessions ADD COLUMN IF NOT EXISTS bridge_token_sha256 text;
CREATE UNIQUE INDEX IF NOT EXISTS dz_voice_bridge_grant ON dz_native_voice_sessions(bridge_token_sha256) WHERE bridge_token_sha256 IS NOT NULL;
