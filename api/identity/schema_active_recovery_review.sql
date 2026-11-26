-- REVIEW ONLY: install after individual import activation and pending recovery.
-- No account changes or recovery authorization are performed by this schema.
BEGIN;
SET LOCAL lock_timeout='7s';
SET LOCAL statement_timeout='25s';
SELECT pg_advisory_xact_lock(739110211);
DO $$ BEGIN
 IF to_regclass('public.app_users') IS NOT NULL
 OR to_regclass('public.identity_recovery_authority') IS NULL
 OR to_regclass('public.identity_import_activation_receipts') IS NULL
 THEN RAISE EXCEPTION 'Unexpected active recovery target'; END IF;
END $$;
CREATE TABLE public.identity_active_recovery_authority (
 subject varchar(160) PRIMARY KEY REFERENCES public.identity_accounts(subject),
 approved_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 approved_by name NOT NULL DEFAULT session_user,
 revoked_at timestamptz
);
-- Native accounts have no former credential authority. Imported accounts
-- require the separate operator record AFTER verified source handoff.
CREATE TABLE public.identity_active_recovery_challenges (
 token_hash char(64) PRIMARY KEY,
 subject varchar(160) NOT NULL REFERENCES public.identity_accounts(subject),
 email varchar(320) NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 expires_at timestamptz NOT NULL,
 consumed_at timestamptz,
 CHECK(expires_at>created_at AND expires_at<=created_at+interval '30 minutes')
);
CREATE INDEX identity_active_recovery_subject_idx ON public.identity_active_recovery_challenges(subject,created_at);
CREATE TABLE public.identity_credential_revocations (
 subject varchar(160) PRIMARY KEY REFERENCES public.identity_accounts(subject),
 revoked_at timestamptz NOT NULL
);
REVOKE ALL ON public.identity_active_recovery_authority,public.identity_active_recovery_challenges,
 public.identity_credential_revocations FROM PUBLIC,dz_identity_api;
GRANT SELECT(subject,revoked_at) ON public.identity_credential_revocations TO dz_identity_api;

CREATE FUNCTION public.issue_active_recovery(p_email text,p_digest text)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $fn$
DECLARE a public.identity_accounts%ROWTYPE;
BEGIN
 IF p_digest IS NULL OR p_digest !~ '^[0-9a-f]{64}$' THEN RETURN NULL; END IF;
 SELECT * INTO a FROM public.identity_accounts x
 WHERE x.email=p_email AND x.email_verified_at IS NOT NULL
 AND x.status='active' AND x.source_active FOR UPDATE;
 IF NOT FOUND THEN RETURN NULL; END IF;
 IF a.identity_origin='operly_import' THEN
   PERFORM 1 FROM public.identity_active_recovery_authority g WHERE g.subject=a.subject
   AND g.revoked_at IS NULL FOR UPDATE;
   IF NOT FOUND OR a.import_activation_receipt_id IS NULL THEN RETURN NULL; END IF;
 ELSIF a.identity_origin<>'native_google' THEN RETURN NULL;
 END IF;
 IF (SELECT count(*) FROM public.identity_active_recovery_challenges
 WHERE subject=a.subject AND created_at>clock_timestamp()-interval '1 hour')>=3 THEN RETURN NULL; END IF;
 INSERT INTO public.identity_active_recovery_challenges(token_hash,subject,email,expires_at)
 VALUES(p_digest,a.subject,a.email,clock_timestamp()+interval '20 minutes');
 RETURN a.email;
END $fn$;
CREATE FUNCTION public.redeem_active_recovery(p_email text,p_digest text,p_hash text)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $fn$
DECLARE a public.identity_accounts%ROWTYPE;
        sid text;
        rev timestamptz;
BEGIN
 IF p_digest IS NULL OR p_digest !~ '^[0-9a-f]{64}$'
 OR p_hash IS NULL OR left(p_hash,10)<>'$argon2id$' OR length(p_hash)>512 THEN RETURN FALSE; END IF;
 SELECT subject INTO sid FROM public.identity_active_recovery_challenges WHERE token_hash=p_digest;
 IF NOT FOUND THEN RETURN FALSE; END IF;
 SELECT * INTO a FROM public.identity_accounts x WHERE x.subject=sid AND x.email=p_email
 AND x.email_verified_at IS NOT NULL AND x.status='active' AND x.source_active FOR UPDATE;
 IF NOT FOUND THEN RETURN FALSE; END IF;
 IF a.identity_origin='operly_import' THEN
   PERFORM 1 FROM public.identity_active_recovery_authority g WHERE g.subject=a.subject
   AND g.revoked_at IS NULL FOR UPDATE;
   IF NOT FOUND OR a.import_activation_receipt_id IS NULL THEN RETURN FALSE; END IF;
 ELSIF a.identity_origin<>'native_google' THEN RETURN FALSE;
 END IF;
 UPDATE public.identity_active_recovery_challenges SET consumed_at=clock_timestamp()
 WHERE token_hash=p_digest AND subject=sid AND email=a.email AND consumed_at IS NULL
 AND expires_at>clock_timestamp();
 IF NOT FOUND THEN RETURN FALSE; END IF;
 rev:=clock_timestamp();
 UPDATE public.identity_accounts SET password_hash=p_hash WHERE subject=sid;
 INSERT INTO public.identity_credential_revocations(subject,revoked_at) VALUES(sid,rev)
 ON CONFLICT(subject) DO UPDATE SET revoked_at=EXCLUDED.revoked_at;
 UPDATE public.identity_active_recovery_challenges SET consumed_at=rev WHERE subject=sid AND consumed_at IS NULL;
 UPDATE public.identity_browser_sessions SET revoked_at=rev WHERE subject=sid AND revoked_at IS NULL;
 UPDATE public.identity_authorization_codes SET consumed_at=rev WHERE subject=sid AND consumed_at IS NULL;
 UPDATE public.identity_refresh_grants SET revoked_at=rev WHERE subject=sid AND revoked_at IS NULL;
 RETURN TRUE;
END $fn$;
REVOKE ALL ON FUNCTION public.issue_active_recovery(text,text),public.redeem_active_recovery(text,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.issue_active_recovery(text,text),public.redeem_active_recovery(text,text,text) TO dz_identity_api;
COMMIT;
