-- REVIEW ONLY. Dedicated identity DB, after the individual activation schema.
-- Operator grants recovery authority for a reconciled immutable subject, not
-- for arbitrary submitted email. No active-account password resets here.
BEGIN;
SET LOCAL lock_timeout='7s';
SET LOCAL statement_timeout='25s';
SELECT pg_advisory_xact_lock(739110211);
DO $$ BEGIN
 IF to_regclass('public.app_users') IS NOT NULL
 OR to_regclass('public.identity_import_proofs') IS NULL
 OR NOT EXISTS (SELECT 1 FROM pg_constraint WHERE
   conrelid=to_regclass('public.identity_accounts')
   AND conname='identity_import_requires_individual_approval' AND convalidated)
 OR EXISTS (SELECT 1 FROM pg_roles WHERE rolname='dz_identity_recovery_sync' AND rolcanlogin)
 THEN RAISE EXCEPTION 'Unexpected recovery authority state'; END IF;
END $$;
CREATE TABLE public.identity_recovery_authority (
 subject varchar(160) PRIMARY KEY REFERENCES public.identity_accounts(subject),
 email varchar(320) NOT NULL,
 approved_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 approved_by name NOT NULL DEFAULT session_user,
 expires_at timestamptz NOT NULL,
 revoked_at timestamptz,
 CHECK(expires_at>approved_at AND expires_at<=approved_at+interval '7 days')
);
CREATE TABLE public.identity_recovery_challenges (
 token_hash char(64) PRIMARY KEY,
 subject varchar(160) NOT NULL REFERENCES public.identity_recovery_authority(subject),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 expires_at timestamptz NOT NULL,
 consumed_at timestamptz,
 CHECK(expires_at>created_at AND expires_at<=created_at+interval '30 minutes')
);
CREATE INDEX identity_recovery_challenge_subject_idx ON public.identity_recovery_challenges(subject,created_at);
REVOKE ALL ON public.identity_recovery_authority,public.identity_recovery_challenges FROM PUBLIC,dz_identity_api;
-- Only the operator can approve recovery authority. Do so after fresh source
-- reconciliation and a verified source recovery handoff for this subject.
-- Functions expose no password hash or token to callers.
CREATE FUNCTION public.issue_pending_recovery(p_email text,p_digest text)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $fn$
DECLARE a public.identity_accounts%ROWTYPE;
BEGIN
 IF p_digest IS NULL OR p_digest !~ '^[0-9a-f]{64}$' THEN RETURN NULL; END IF;
 SELECT x.* INTO a FROM public.identity_accounts x
 JOIN public.identity_recovery_authority g ON g.subject=x.subject
 WHERE x.email=p_email AND x.email=g.email AND x.email_verified_at IS NOT NULL
 AND x.status='pending' AND x.source_active AND x.identity_origin='operly_import'
 AND x.subject=x.source_operly_user_id AND x.password_hash IS NULL
 AND g.revoked_at IS NULL AND g.expires_at>clock_timestamp()
 FOR UPDATE OF x,g;
 IF NOT FOUND THEN RETURN NULL; END IF;
 IF (SELECT count(*) FROM public.identity_recovery_challenges
 WHERE subject=a.subject AND created_at>clock_timestamp()-interval '1 hour')>=3
 THEN RETURN NULL; END IF;
 INSERT INTO public.identity_recovery_challenges(token_hash,subject,expires_at)
 VALUES(p_digest,a.subject,clock_timestamp()+interval '20 minutes');
 RETURN a.email;
END $fn$;
CREATE FUNCTION public.redeem_pending_recovery(p_email text,p_digest text,p_hash text,p_proof uuid)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $fn$
DECLARE sid text;
BEGIN
 IF p_digest IS NULL OR p_digest !~ '^[0-9a-f]{64}$'
 OR p_hash IS NULL OR left(p_hash,10)<>'$argon2id$' OR length(p_hash)>512
 OR p_proof IS NULL THEN RETURN FALSE; END IF;
 SELECT subject INTO sid FROM public.identity_recovery_challenges WHERE token_hash=p_digest;
 IF NOT FOUND THEN RETURN FALSE; END IF;
 -- Same lock order as issuance, then recheck token and authority.
 PERFORM 1 FROM public.identity_accounts a JOIN public.identity_recovery_authority g
 ON a.subject=g.subject WHERE a.subject=sid AND a.email=p_email AND a.email=g.email AND a.email_verified_at IS NOT NULL
 AND a.status='pending' AND a.source_active AND a.identity_origin='operly_import'
 AND a.subject=a.source_operly_user_id AND a.password_hash IS NULL
 AND g.revoked_at IS NULL AND g.expires_at>clock_timestamp() FOR UPDATE OF a,g;
 IF NOT FOUND THEN RETURN FALSE; END IF;
 UPDATE public.identity_recovery_challenges SET consumed_at=clock_timestamp()
 WHERE token_hash=p_digest AND subject=sid AND consumed_at IS NULL AND expires_at>clock_timestamp();
 IF NOT FOUND THEN RETURN FALSE; END IF;
 UPDATE public.identity_accounts SET password_hash=p_hash WHERE subject=sid;
 -- Invalidate sibling codes. No login session or activation is created.
 UPDATE public.identity_recovery_challenges SET consumed_at=clock_timestamp()
 WHERE subject=sid AND consumed_at IS NULL;
 INSERT INTO public.identity_import_proofs(proof_id,subject,proof_method)
 VALUES(p_proof,sid,'password');
 RETURN TRUE;
END $fn$;
REVOKE ALL ON FUNCTION public.issue_pending_recovery(text,text),
 public.redeem_pending_recovery(text,text,text,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.issue_pending_recovery(text,text),
 public.redeem_pending_recovery(text,text,text,uuid) TO dz_identity_api;
COMMIT;
