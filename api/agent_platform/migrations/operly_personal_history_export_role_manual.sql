-- Review and run ONLY on the Operly source database.
-- Views intentionally exclude workspaces, guests, tool traces and artifacts.
BEGIN;
SET LOCAL lock_timeout='7s';
SET LOCAL statement_timeout='25s';
DO $$
BEGIN
 IF to_regclass('public.app_users') IS NULL
    OR to_regclass('public.agent_chat_conversations') IS NULL
    OR to_regclass('public.agent_chat_messages') IS NULL
    OR to_regclass('public.identity_accounts') IS NOT NULL
    OR EXISTS(SELECT 1 FROM pg_roles WHERE rolname='dz_personal_history_export')
 THEN RAISE EXCEPTION 'Unexpected personal history source'; END IF;
END $$;
CREATE ROLE dz_personal_history_export NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
 NOREPLICATION NOBYPASSRLS NOINHERIT;
ALTER ROLE dz_personal_history_export SET search_path TO pg_catalog,public;
ALTER ROLE dz_personal_history_export SET default_transaction_read_only TO on;
DO $$ BEGIN
 EXECUTE format('GRANT CONNECT ON DATABASE %I TO dz_personal_history_export',current_database());
END $$;
GRANT USAGE ON SCHEMA public TO dz_personal_history_export;
CREATE VIEW public.dz_personal_history_export_conversations WITH (security_barrier=true) AS
 SELECT c.id::text AS id,c.owner_user_id::text AS owner_id,c.title,c.created_at,c.updated_at,c.channel,c.surface
 FROM public.agent_chat_conversations c JOIN public.app_users u ON u.id=c.owner_user_id
 WHERE c.scope_kind='personal' AND c.workspace_id IS NULL
   AND (c.authority_user_id IS NULL OR c.authority_user_id=c.owner_user_id);
CREATE VIEW public.dz_personal_history_export_messages WITH (security_barrier=true) AS
 SELECT m.id::text AS id,m.conversation_id::text AS conversation_id,c.owner_id,
        m.role,m.content,m.created_at
 FROM public.agent_chat_messages m JOIN public.dz_personal_history_export_conversations c
 ON c.id=m.conversation_id;
REVOKE ALL ON public.dz_personal_history_export_conversations,public.dz_personal_history_export_messages FROM PUBLIC;
GRANT SELECT ON public.dz_personal_history_export_conversations,public.dz_personal_history_export_messages TO dz_personal_history_export;
COMMIT;
