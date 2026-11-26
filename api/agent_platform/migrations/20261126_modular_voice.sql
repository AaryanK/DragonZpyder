-- Reuse the existing voice reservation table; no raw login token or audio.
ALTER TABLE dz_native_voice_sessions ADD COLUMN IF NOT EXISTS transport text NOT NULL DEFAULT 'realtime';
ALTER TABLE dz_native_voice_sessions ADD COLUMN IF NOT EXISTS session_reference text;
ALTER TABLE dz_native_voice_sessions ADD COLUMN IF NOT EXISTS room_name text;
ALTER TABLE dz_native_voice_sessions ADD COLUMN IF NOT EXISTS worker_nonce_sha256 text;
CREATE UNIQUE INDEX IF NOT EXISTS dz_modular_voice_room ON dz_native_voice_sessions(room_name) WHERE room_name IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS dz_modular_voice_session ON dz_native_voice_sessions(session_id) WHERE transport='modular';
