-- REVIEW ONLY. Do not apply until fresh source reconciliation, independent
-- proof collection, operator approval and rollback review are complete.
-- Unlike the former script, this never removes the pending fence without
-- replacing it with a per-subject activation receipt constraint.
BEGIN;
SET LOCAL lock_timeout = '7s';
SET LOCAL statement_timeout = '25s';
SELECT pg_advisory_xact_lock(739110211);

DO $$
BEGIN
 IF to_regclass('public.app_users') IS NOT NULL
    OR to_regclass('public.identity_accounts') IS NULL
    OR to_regclass('public.identity_import_activation_receipts') IS NOT NULL
    OR NOT EXISTS (SELECT 1 FROM pg_constraint
          WHERE conrelid=to_regclass('public.identity_accounts')
            AND conname='identity_import_not_automatically_active' AND convalidated)
    OR EXISTS (SELECT 1 FROM public.identity_accounts
                WHERE identity_origin <> 'operly_import' OR status <> 'pending')
    OR EXISTS (SELECT 1 FROM public.identity_oauth_clients WHERE enabled)
    OR NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='dz_identity_api')
 THEN RAISE EXCEPTION 'Unexpected identity database or cutover state';
 END IF;
END $$;

-- No bearer token, password, email or provider subject is stored here.
-- This is operator attestation, not itself proof of a user's identity.
CREATE TABLE public.identity_import_activation_receipts (
 subject varchar(160) PRIMARY KEY REFERENCES public.identity_accounts(subject) ON DELETE RESTRICT,
 receipt_id uuid NOT NULL UNIQUE,
 proof_method text NOT NULL CHECK (proof_method IN ('password','google','legacy_reauth')),
 proof_at timestamptz NOT NULL,
 approved_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 approved_by name NOT NULL DEFAULT session_user,
 CONSTRAINT identity_activation_receipt_fresh CHECK (
     proof_at <= approved_at AND approved_at - proof_at <= interval '15 minutes'),
 UNIQUE(subject,receipt_id)
);
REVOKE ALL ON public.identity_import_activation_receipts FROM PUBLIC, dz_identity_api;
ALTER TABLE public.identity_import_activation_receipts ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.identity_accounts
 ADD COLUMN import_activation_receipt_id uuid;
ALTER TABLE public.identity_accounts
 ADD CONSTRAINT identity_import_activation_receipt_fk
 FOREIGN KEY(subject,import_activation_receipt_id)
 REFERENCES public.identity_import_activation_receipts(subject,receipt_id)
 ON DELETE RESTRICT;
ALTER TABLE public.identity_accounts
 ADD CONSTRAINT identity_import_requires_individual_approval CHECK (
   (identity_origin='operly_import' AND (status<>'active' OR
      (source_active AND import_activation_receipt_id IS NOT NULL)))
   OR (identity_origin='native_google' AND import_activation_receipt_id IS NULL)
 );
ALTER TABLE public.identity_accounts
 DROP CONSTRAINT identity_import_not_automatically_active;

-- Operator-only primitive: the caller MUST already have fresh independently
-- verified proof of this exact immutable subject. Do not expose as an HTTP
-- endpoint or use an agent's assertion as proof. This function performs no
-- authentication itself. No API or temporary migration role receives EXECUTE.
CREATE FUNCTION public.approve_imported_identity(
 p_subject text, p_receipt uuid, p_method text, p_proof_at timestamptz
) RETURNS void LANGUAGE plpgsql SECURITY INVOKER
 SET search_path = pg_catalog, public AS $fn$
DECLARE a public.identity_accounts%ROWTYPE;
BEGIN
 IF p_receipt IS NULL OR p_proof_at IS NULL
    OR p_proof_at > clock_timestamp()
    OR p_proof_at < clock_timestamp() - interval '15 minutes'
    OR p_method IS NULL OR p_method NOT IN ('password','google','legacy_reauth')
 THEN RAISE EXCEPTION 'Fresh individual approval required'; END IF;
 SELECT * INTO a FROM public.identity_accounts
 WHERE subject=p_subject AND source_operly_user_id=p_subject
   AND identity_origin='operly_import' AND status='pending' AND source_active
 FOR UPDATE;
 IF NOT FOUND OR a.import_activation_receipt_id IS NOT NULL
 THEN RAISE EXCEPTION 'Pending eligible identity required'; END IF;
 IF p_method='password' AND a.password_hash IS NULL
 THEN RAISE EXCEPTION 'Password proof unavailable'; END IF;
 IF p_method='google' AND NOT EXISTS (
    SELECT 1 FROM public.identity_provider_links WHERE subject=p_subject
     AND provider='google' AND source='auth' AND login_eligible)
 THEN RAISE EXCEPTION 'Google proof unavailable'; END IF;
 -- Legacy reauthentication requires a separate reviewed source-authority
 -- proof protocol. Refuse it until that protocol exists.
 IF p_method='legacy_reauth'
 THEN RAISE EXCEPTION 'Legacy proof protocol not enabled'; END IF;
 INSERT INTO public.identity_import_activation_receipts
  (subject,receipt_id,proof_method,proof_at)
 VALUES (p_subject,p_receipt,p_method,p_proof_at);
 UPDATE public.identity_accounts
 SET status='active',import_activation_receipt_id=p_receipt
 WHERE subject=p_subject AND status='pending';
 IF NOT FOUND THEN RAISE EXCEPTION 'Activation did not complete'; END IF;
END
$fn$;
REVOKE ALL ON FUNCTION public.approve_imported_identity(text,uuid,text,timestamptz)
 FROM PUBLIC, dz_identity_api;

-- Deployment of this schema alone must not activate any user.
DO $$
BEGIN
 IF EXISTS(SELECT 1 FROM public.identity_accounts WHERE status='active')
    OR EXISTS(SELECT 1 FROM public.identity_import_activation_receipts)
 THEN RAISE EXCEPTION 'Unexpected activation'; END IF;
END $$;
COMMIT;
