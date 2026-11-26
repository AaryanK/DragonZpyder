-- Manual, reviewed, temporary credential synchronization role.
-- Use only while every imported account is still pending and source writes are controlled.
BEGIN;
SET LOCAL lock_timeout='7s';
SET LOCAL statement_timeout='25s';
SELECT pg_advisory_xact_lock(739110211);
DO $$
BEGIN
 IF to_regclass('public.app_users') IS NOT NULL
    OR to_regclass('public.identity_accounts') IS NULL
    OR NOT EXISTS (SELECT 1 FROM pg_constraint WHERE
       conrelid=to_regclass('public.identity_accounts') AND
       conname='identity_import_not_automatically_active' AND convalidated)
    OR EXISTS (SELECT 1 FROM public.identity_accounts WHERE status<>'pending' OR identity_origin<>'operly_import')
    OR EXISTS (SELECT 1 FROM public.identity_oauth_clients WHERE enabled)
    OR EXISTS (SELECT 1 FROM pg_roles WHERE rolname='dz_identity_recovery_sync')
 THEN RAISE EXCEPTION 'Unexpected recovery synchronization target'; END IF;
END $$;
CREATE ROLE dz_identity_recovery_sync NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT;
ALTER ROLE dz_identity_recovery_sync SET search_path TO pg_catalog,public;
DO $$ BEGIN
 EXECUTE format('GRANT CONNECT ON DATABASE %I TO dz_identity_recovery_sync',current_database());
END $$;
GRANT USAGE ON SCHEMA public TO dz_identity_recovery_sync;
GRANT SELECT(subject,source_operly_user_id,identity_origin,status,email,password_hash,
 display_name,email_verified_at,source_active) ON public.identity_accounts TO dz_identity_recovery_sync;
GRANT SELECT(subject,provider,provider_subject,source,login_eligible)
 ON public.identity_provider_links TO dz_identity_recovery_sync;
GRANT SELECT(enabled) ON public.identity_oauth_clients TO dz_identity_recovery_sync;
GRANT UPDATE(password_hash) ON public.identity_accounts TO dz_identity_recovery_sync;
CREATE POLICY dz_recovery_read_accounts ON public.identity_accounts
 FOR SELECT TO dz_identity_recovery_sync USING(true);
CREATE POLICY dz_recovery_read_links ON public.identity_provider_links
 FOR SELECT TO dz_identity_recovery_sync USING(true);
CREATE POLICY dz_recovery_add_password ON public.identity_accounts
 FOR UPDATE TO dz_identity_recovery_sync
 USING(status='pending' AND identity_origin='operly_import' AND subject=source_operly_user_id
   AND source_active AND email_verified_at IS NOT NULL AND password_hash IS NULL)
 WITH CHECK(status='pending' AND identity_origin='operly_import' AND subject=source_operly_user_id
   AND source_active AND email_verified_at IS NOT NULL AND password_hash IS NOT NULL
   AND (left(password_hash,10)='$argon2id$' OR left(password_hash,14)='pbkdf2_sha256$'));
COMMIT;
