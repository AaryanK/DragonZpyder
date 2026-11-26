-- Optional profile-only metadata. REVIEW AND APPLY BY IDENTITY DB OPERATOR.
-- Do not run at startup or enable the feature before the restricted role and
-- current identity schema are verified. Roll back by disabling the flag first.
BEGIN;
SET LOCAL lock_timeout = '7s';
SET LOCAL statement_timeout = '30s';
ALTER TABLE public.identity_accounts
 ADD COLUMN IF NOT EXISTS google_avatar_url VARCHAR(2048);
GRANT UPDATE (google_avatar_url) ON public.identity_accounts TO dz_identity_api;
COMMIT;
-- No account activation, provider linking, grants over email or status, or
-- role changes. Existing account UPDATE RLS remains active.
