-- Operator-only, expiring Personal principals for authorized production tests.
-- Never run on API startup. No provider claim, Operly mapping or public signup.
-- Apply only after schema_import_activation_review.sql, using the DB owner.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '25s';
SELECT pg_advisory_xact_lock(739110216);
DO $$
BEGIN
 IF to_regclass('public.app_users') IS NOT NULL
    OR NOT EXISTS (SELECT 1 FROM pg_constraint WHERE
        conrelid=to_regclass('public.identity_accounts') AND
        conname='identity_import_requires_individual_approval' AND convalidated)
    OR NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='dz_identity_api')
    OR EXISTS (SELECT 1 FROM pg_attribute WHERE
        attrelid=to_regclass('public.identity_accounts') AND
        attname='operator_test_expires_at' AND NOT attisdropped)
 THEN RAISE EXCEPTION 'Unexpected identity schema or already installed'; END IF;
END $$;

ALTER TABLE public.identity_accounts
 ADD COLUMN operator_test_expires_at timestamptz,
 ADD COLUMN operator_test_provisioned_by name;
ALTER TABLE public.identity_accounts
 DROP CONSTRAINT identity_native_origin_valid,
 DROP CONSTRAINT identity_source_link_consistency,
 DROP CONSTRAINT identity_import_requires_individual_approval;
ALTER TABLE public.identity_accounts
 ADD CONSTRAINT identity_native_origin_valid CHECK
   (identity_origin IN ('operly_import','native_google','operator_test')),
 ADD CONSTRAINT identity_source_link_consistency CHECK
   ((identity_origin='operly_import' AND source_operly_user_id IS NOT NULL)
    OR (identity_origin IN ('native_google','operator_test') AND source_operly_user_id IS NULL)),
 ADD CONSTRAINT identity_import_requires_individual_approval CHECK
   ((identity_origin='operly_import' AND (status<>'active' OR
      (source_active AND import_activation_receipt_id IS NOT NULL)))
    OR (identity_origin IN ('native_google','operator_test') AND import_activation_receipt_id IS NULL)),
 ADD CONSTRAINT identity_operator_test_boundary CHECK
   ((identity_origin<>'operator_test' AND operator_test_expires_at IS NULL
       AND operator_test_provisioned_by IS NULL)
    OR (identity_origin='operator_test' AND
       subject ~ '^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
       AND email='acceptance-' || subject || '@dragonzpyder.invalid'
       AND password_hash IS NOT NULL AND password_hash LIKE '$argon2id$%'
       AND email_verified_at IS NOT NULL AND operator_test_provisioned_by IS NOT NULL
       AND operator_test_expires_at IS NOT NULL
       AND operator_test_expires_at > created_at
       AND operator_test_expires_at <= created_at + interval '8 hours'));

-- Restrictive policy is ANDed with every existing permissive policy. Expiry
-- therefore invalidates password login, existing cookies and refresh lookups.
-- API cannot extend expiry, provision tests, or change origin/status.
CREATE POLICY dz_identity_operator_test_expiry ON public.identity_accounts
 AS RESTRICTIVE FOR ALL TO dz_identity_api
 USING (identity_origin<>'operator_test' OR operator_test_expires_at>statement_timestamp())
 WITH CHECK (identity_origin<>'operator_test' OR operator_test_expires_at>statement_timestamp());

CREATE FUNCTION public.provision_operator_test_identity(
 p_subject uuid, p_password_hash text, p_minutes integer
) RETURNS timestamptz LANGUAGE plpgsql SECURITY INVOKER
 SET search_path = pg_catalog, public AS $fn$
DECLARE expiry timestamptz;
BEGIN
 IF p_minutes IS NULL OR p_minutes NOT BETWEEN 1 AND 480
    OR p_subject IS NULL OR p_password_hash IS NULL
    OR length(p_password_hash)>512 OR p_password_hash NOT LIKE '$argon2id$%'
 THEN RAISE EXCEPTION 'Bounded test identity parameters required'; END IF;
 expiry := statement_timestamp() + make_interval(mins=>p_minutes);
 INSERT INTO public.identity_accounts
   (subject,source_operly_user_id,identity_origin,email,password_hash,
    display_name,email_verified_at,source_active,status,created_at,
    operator_test_expires_at,operator_test_provisioned_by)
 VALUES (p_subject::text,NULL,'operator_test',
   'acceptance-' || p_subject::text || '@dragonzpyder.invalid',p_password_hash,
   'Engineering acceptance test',statement_timestamp(),TRUE,'active',
   statement_timestamp(),expiry,session_user);
 RETURN expiry;
END $fn$;
REVOKE ALL ON FUNCTION public.provision_operator_test_identity(uuid,text,integer)
 FROM PUBLIC, dz_identity_api;
COMMIT;
