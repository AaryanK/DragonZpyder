-- Operator-only, one-time source export role. Run on the verified Operly identity DB.
-- No password here; provision via a hidden SCRAM prompt, only for the migration window.
BEGIN;
SET LOCAL lock_timeout = '7s';
SET LOCAL statement_timeout = '25s';
DO $$
BEGIN
 IF to_regclass('public.app_users') IS NULL
    OR to_regclass('public.auth_identities') IS NULL
    OR to_regclass('public.identity_accounts') IS NOT NULL
    OR EXISTS (SELECT 1 FROM pg_roles WHERE rolname='dz_identity_export') THEN
   RAISE EXCEPTION 'Unexpected source database or existing export role';
 END IF;
END $$;
CREATE ROLE dz_identity_export NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
 NOREPLICATION NOBYPASSRLS NOINHERIT;
ALTER ROLE dz_identity_export SET search_path TO pg_catalog, public;
ALTER ROLE dz_identity_export SET default_transaction_read_only TO on;
GRANT USAGE ON SCHEMA public TO dz_identity_export;
DO $$ BEGIN
 EXECUTE format('GRANT CONNECT ON DATABASE %I TO dz_identity_export',current_database());
END $$;
GRANT SELECT (id,email,password_hash,display_name,email_verified_at,active)
 ON public.app_users TO dz_identity_export;
GRANT SELECT (user_id,provider,provider_subject)
 ON public.auth_identities TO dz_identity_export;
COMMIT;
