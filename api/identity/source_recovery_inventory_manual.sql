-- Aggregate-only recovery inventory. Run on the verified Operly source DB.
-- No account IDs, emails, password hashes or provider identifiers are returned.
BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout = '30s';
DO $$
BEGIN
 IF to_regclass('public.app_users') IS NULL
    OR to_regclass('public.auth_identities') IS NULL
    OR to_regclass('public.identity_accounts') IS NOT NULL
 THEN RAISE EXCEPTION 'Unexpected source database'; END IF;
END $$;
WITH inventory AS (
 SELECT u.active,
        u.email_verified_at IS NOT NULL AS email_verified,
        u.password_hash IS NOT NULL AS has_password,
        EXISTS (SELECT 1 FROM public.auth_identities a
                WHERE a.user_id=u.id AND a.provider='google') AS has_google,
        EXISTS (SELECT 1 FROM public.auth_identities a
                WHERE a.user_id=u.id AND a.provider='discord') AS has_discord_auth
 FROM public.app_users u
), classified AS (
 SELECT *, (has_google OR (has_password AND email_verified)) AS candidate
 FROM inventory
)
SELECT count(*) AS total_accounts,
       count(*) FILTER (WHERE active) AS active_accounts,
       count(*) FILTER (WHERE active AND candidate) AS native_candidate,
       count(*) FILTER (WHERE active AND NOT candidate) AS recovery_needed,
       count(*) FILTER (WHERE active AND NOT candidate AND email_verified)
         AS recovery_verified_email,
       count(*) FILTER (WHERE active AND NOT candidate AND NOT email_verified)
         AS recovery_unverified_email,
       count(*) FILTER (WHERE active AND NOT candidate AND has_discord_auth)
         AS recovery_discord_auth,
       count(*) FILTER (WHERE active AND has_password AND NOT email_verified)
         AS unverified_password_accounts
FROM classified;
SELECT provider,count(*) FROM public.auth_identities GROUP BY provider ORDER BY provider;
ROLLBACK;
