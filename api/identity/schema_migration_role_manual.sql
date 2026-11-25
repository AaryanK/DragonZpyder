-- Operator-only, temporary insert-only role for the dedicated DragonZpyder identity DB.
-- Do not reuse dz_identity_api or add these credentials to the live API.
BEGIN;
SET LOCAL lock_timeout = '7s';
SET LOCAL statement_timeout = '25s';
SELECT pg_advisory_xact_lock(739110211);
DO $$
BEGIN
 IF to_regclass('public.app_users') IS NOT NULL
    OR to_regclass('public.identity_accounts') IS NULL
    OR NOT EXISTS (SELECT 1 FROM pg_constraint
       WHERE conname='identity_import_not_automatically_active'
       AND conrelid='public.identity_accounts'::regclass AND convalidated)
    OR EXISTS (SELECT 1 FROM public.identity_oauth_clients WHERE enabled)
    OR EXISTS (SELECT 1 FROM public.identity_accounts)
    OR EXISTS (SELECT 1 FROM public.identity_provider_links)
    OR NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='dz_identity_api')
    OR EXISTS (SELECT 1 FROM pg_roles WHERE rolname='dz_identity_migration')
    OR (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON c.relnamespace=n.oid
        WHERE n.nspname='public' AND c.relname IN ('identity_accounts','identity_provider_links')
          AND c.relrowsecurity) <> 2 THEN
   RAISE EXCEPTION 'Unexpected target or activation guard';
 END IF;
END $$;
CREATE ROLE dz_identity_migration NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
 NOREPLICATION NOBYPASSRLS NOINHERIT;
ALTER ROLE dz_identity_migration SET search_path TO pg_catalog, public;
DO $$ BEGIN
 EXECUTE format('GRANT CONNECT ON DATABASE %I TO dz_identity_migration',current_database());
END $$;
GRANT USAGE ON SCHEMA public TO dz_identity_migration;
GRANT SELECT (subject,status) ON public.identity_accounts TO dz_identity_migration;
GRANT SELECT (id) ON public.identity_provider_links TO dz_identity_migration;
GRANT SELECT (subject) ON public.identity_browser_sessions,
 public.identity_authorization_codes, public.identity_refresh_grants TO dz_identity_migration;
GRANT SELECT (enabled) ON public.identity_oauth_clients TO dz_identity_migration;
GRANT INSERT (subject,source_operly_user_id,identity_origin,email,password_hash,display_name,
 email_verified_at,source_active,status) ON public.identity_accounts TO dz_identity_migration;
GRANT INSERT (subject,provider,provider_subject,source,login_eligible)
 ON public.identity_provider_links TO dz_identity_migration;
GRANT USAGE ON SEQUENCE public.identity_provider_links_id_seq TO dz_identity_migration;
CREATE POLICY dz_identity_migration_accounts_read ON public.identity_accounts
 FOR SELECT TO dz_identity_migration USING (true);
CREATE POLICY dz_identity_migration_accounts_insert ON public.identity_accounts
 FOR INSERT TO dz_identity_migration WITH CHECK (
 identity_origin='operly_import' AND subject=source_operly_user_id AND status='pending');
CREATE POLICY dz_identity_migration_links_read ON public.identity_provider_links
 FOR SELECT TO dz_identity_migration USING (true);
CREATE POLICY dz_identity_migration_links_insert ON public.identity_provider_links
 FOR INSERT TO dz_identity_migration WITH CHECK (
 provider='google' AND source='auth' AND login_eligible AND EXISTS (
 SELECT 1 FROM public.identity_accounts a
 WHERE a.subject=identity_provider_links.subject AND a.status='pending'));
COMMIT;
