-- Manual privileged operation on the dedicated identity DB ONLY.
-- No password in SQL, logs, source control or application process.
-- Role starts NOLOGIN; operator sets SCRAM password out of band.
BEGIN;
SET LOCAL lock_timeout = '7s';
SET LOCAL statement_timeout = '30s';
SELECT pg_advisory_xact_lock(739110213);
DO $$
BEGIN
 IF current_schema() <> 'public'
    OR (SELECT count(*) FROM pg_tables WHERE schemaname='public'
       AND tablename IN ('identity_accounts','identity_provider_links',
       'identity_browser_sessions','identity_oauth_clients','identity_authorization_codes',
       'identity_refresh_grants','identity_provider_challenges','identity_authorization_interactions',
       'identity_login_rate_limits')) <> 9
    OR NOT EXISTS (SELECT 1 FROM pg_constraint
       WHERE conname='identity_import_not_automatically_active'
       AND conrelid='public.identity_accounts'::regclass)
    OR EXISTS (SELECT 1 FROM pg_roles WHERE rolname='dz_identity_api') THEN
   RAISE EXCEPTION 'Unexpected identity database or role; review before provisioning';
 END IF;
END $$;
CREATE ROLE dz_identity_api NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT;
-- This is an isolated database. Prevent public DDL and temporary tables.
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
DO $$ BEGIN
 EXECUTE format('REVOKE CREATE, TEMPORARY ON DATABASE %I FROM PUBLIC', current_database());
 EXECUTE format('GRANT CONNECT ON DATABASE %I TO dz_identity_api', current_database());
END $$;
ALTER ROLE dz_identity_api SET search_path TO pg_catalog, public;
GRANT USAGE ON SCHEMA public TO dz_identity_api;
GRANT SELECT ON public.identity_accounts, public.identity_provider_links,
 public.identity_browser_sessions, public.identity_oauth_clients,
 public.identity_authorization_codes, public.identity_refresh_grants,
 public.identity_provider_challenges, public.identity_authorization_interactions,
 public.identity_login_rate_limits TO dz_identity_api;
GRANT INSERT (subject,source_operly_user_id,identity_origin,email,password_hash,display_name,
 email_verified_at,source_active,status) ON public.identity_accounts TO dz_identity_api;
GRANT UPDATE (display_name,password_hash) ON public.identity_accounts TO dz_identity_api;
GRANT INSERT (subject,provider,provider_subject,source,login_eligible)
 ON public.identity_provider_links TO dz_identity_api;
GRANT INSERT ON public.identity_browser_sessions, public.identity_authorization_codes,
 public.identity_refresh_grants, public.identity_provider_challenges,
 public.identity_authorization_interactions, public.identity_login_rate_limits TO dz_identity_api;
GRANT UPDATE (revoked_at) ON public.identity_browser_sessions TO dz_identity_api;
GRANT UPDATE (consumed_at) ON public.identity_authorization_codes,
 public.identity_provider_challenges, public.identity_authorization_interactions TO dz_identity_api;
GRANT UPDATE (consumed_at,revoked_at) ON public.identity_refresh_grants TO dz_identity_api;
GRANT UPDATE (attempt_count,window_started_at) ON public.identity_login_rate_limits TO dz_identity_api;
-- Identity sequence permissions are deliberately scoped to this one table.
GRANT USAGE ON SEQUENCE public.identity_provider_links_id_seq TO dz_identity_api;
ALTER TABLE public.identity_accounts ENABLE ROW LEVEL SECURITY;
CREATE POLICY dz_identity_account_read ON public.identity_accounts FOR SELECT TO dz_identity_api USING (true);
CREATE POLICY dz_identity_account_register ON public.identity_accounts FOR INSERT TO dz_identity_api
 WITH CHECK (identity_origin='native_google' AND source_operly_user_id IS NULL
 AND status='active' AND source_active AND email_verified_at IS NOT NULL AND password_hash IS NULL);
CREATE POLICY dz_identity_account_edit ON public.identity_accounts FOR UPDATE TO dz_identity_api
 USING (status='active' AND source_active) WITH CHECK (status='active' AND source_active);
ALTER TABLE public.identity_provider_links ENABLE ROW LEVEL SECURITY;
CREATE POLICY dz_identity_link_read ON public.identity_provider_links FOR SELECT TO dz_identity_api USING (true);
CREATE POLICY dz_identity_link_register ON public.identity_provider_links FOR INSERT TO dz_identity_api
 WITH CHECK (provider='google' AND source='auth' AND login_eligible AND EXISTS
 (SELECT 1 FROM public.identity_accounts a WHERE a.subject=identity_provider_links.subject
 AND a.identity_origin='native_google' AND a.source_operly_user_id IS NULL AND a.status='active'));
COMMIT;
