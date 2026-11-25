-- Manual reviewed migration on the agent checkpoint DB, not on API startup.
-- No messages are copied or deleted by this DDL.
BEGIN;
SET LOCAL lock_timeout='7s';
SET LOCAL statement_timeout='30s';
SELECT pg_advisory_xact_lock(739110215);
ALTER TABLE public.dz_first_party_conversations
 ADD COLUMN IF NOT EXISTS archived_import boolean NOT NULL DEFAULT false;
CREATE TABLE IF NOT EXISTS public.dz_imported_personal_messages (
 conversation_id uuid NOT NULL REFERENCES public.dz_first_party_conversations(id) ON DELETE RESTRICT,
 source_message_id uuid NOT NULL,
 ordinal integer NOT NULL CHECK (ordinal > 0),
 role text NOT NULL CHECK(role IN ('user','assistant')),
 content text NOT NULL,
 created_at timestamptz NOT NULL,
 PRIMARY KEY(conversation_id, source_message_id),
 UNIQUE(conversation_id, ordinal)
);
REVOKE ALL ON public.dz_imported_personal_messages FROM PUBLIC;
COMMIT;
