-- Review and run ONLY on DragonZpyder's dedicated AGENT checkpoint database.
-- This creates a display-only archive; no graph, tool, session or grant changes.
-- Apply 20261122_first_party_chat.sql separately first if necessary.
BEGIN;
SET LOCAL lock_timeout='7s';
SET LOCAL statement_timeout='25s';
SELECT pg_advisory_xact_lock(739110212);
DO $$
BEGIN
 IF to_regclass('public.dz_first_party_conversations') IS NULL
    OR to_regclass('public.agent_chat_conversations') IS NOT NULL
    OR to_regclass('public.identity_accounts') IS NOT NULL
    OR EXISTS(SELECT 1 FROM pg_roles WHERE rolname='dz_personal_history_import')
 THEN RAISE EXCEPTION 'Unexpected archive destination'; END IF;
END $$;
CREATE ROLE dz_personal_history_import NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
 NOREPLICATION NOBYPASSRLS NOINHERIT;
ALTER ROLE dz_personal_history_import SET search_path TO pg_catalog,public;
DO $$ BEGIN
 EXECUTE format('GRANT CONNECT ON DATABASE %I TO dz_personal_history_import',current_database());
END $$;
GRANT USAGE ON SCHEMA public TO dz_personal_history_import;
CREATE TABLE public.dz_imported_personal_conversations (
 id uuid PRIMARY KEY, owner_id text NOT NULL, title text NOT NULL CHECK(length(title) BETWEEN 1 AND 250),
 created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
 channel text NOT NULL, surface text NOT NULL, UNIQUE(id,owner_id));
CREATE INDEX dz_imported_personal_owner_idx ON public.dz_imported_personal_conversations(owner_id,updated_at DESC);
CREATE TABLE public.dz_imported_personal_messages (
 id uuid PRIMARY KEY, conversation_id uuid NOT NULL, owner_id text NOT NULL,
 role text NOT NULL CHECK(role IN ('user','assistant')),
 content text NOT NULL CHECK(octet_length(content)<=1048576), created_at timestamptz NOT NULL,
 FOREIGN KEY(conversation_id,owner_id) REFERENCES public.dz_imported_personal_conversations(id,owner_id) ON DELETE RESTRICT);
CREATE INDEX dz_imported_personal_message_order_idx ON public.dz_imported_personal_messages(conversation_id,owner_id,created_at,id);
REVOKE ALL ON public.dz_imported_personal_conversations,public.dz_imported_personal_messages FROM PUBLIC;
GRANT SELECT,INSERT ON public.dz_imported_personal_conversations,public.dz_imported_personal_messages TO dz_personal_history_import;
GRANT SELECT(id,owner_id) ON public.dz_first_party_conversations TO dz_personal_history_import;
-- Do not grant runtime access until source ownership and browser acceptance review.
COMMIT;
