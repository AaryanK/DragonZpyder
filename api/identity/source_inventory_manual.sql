-- Read-only, aggregate-only inventory. Run on Operly's verified identity database.
-- No emails, UUIDs, password hashes, provider subjects or other row-level data are returned.
BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout = '30s';
DO $$
BEGIN
 IF to_regclass('public.app_users') IS NULL
    OR to_regclass('public.auth_identities') IS NULL
    OR to_regclass('public.identity_accounts') IS NOT NULL THEN
    RAISE EXCEPTION 'Unexpected source database';
 END IF;
END $$;
WITH users AS (
 SELECT id::text AS id, email, password_hash, display_name, active,
        CASE WHEN password_hash IS NULL THEN 'absent'
             WHEN length(password_hash) NOT BETWEEN 1 AND 2048 THEN 'malformed'
             WHEN left(password_hash,length('$argon2id
               THEN 'candidate'
             ELSE 'unsupported' END AS password_kind
 FROM public.app_users
), google AS (
 SELECT user_id::text AS user_id, provider_subject
 FROM public.auth_identities WHERE provider='google'
)
SELECT
 (SELECT count(*) FROM users) AS accounts,
 (SELECT count(*) FROM google) AS google_links,
 (SELECT count(*) FROM users WHERE password_kind='unsupported') AS unsupported_passwords,
 (SELECT count(*) FROM users WHERE password_kind='malformed') AS malformed_passwords,
 (SELECT count(*) FROM users WHERE password_kind='candidate') AS candidate_passwords,
 (SELECT count(*) FROM users WHERE password_kind='absent') AS absent_passwords,
 (SELECT count(*) FROM users u WHERE password_kind IN ('absent','unsupported','malformed')
    AND NOT EXISTS (SELECT 1 FROM google g WHERE g.user_id=u.id)) AS accounts_without_candidate_login,
 (SELECT count(*) FROM users WHERE active IS DISTINCT FROM TRUE) AS inactive_accounts,
 (SELECT count(*) FROM users WHERE id IS NULL OR id !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$') AS invalid_uuid,
 (SELECT count(*) FROM users WHERE email IS NULL OR email<>lower(email)
    OR email<>btrim(email) OR length(email) NOT BETWEEN 1 AND 320 OR position('@' in email)=0) AS invalid_email,
 (SELECT count(*) FROM users WHERE display_name IS NULL OR display_name<>btrim(display_name)
    OR length(display_name) NOT BETWEEN 1 AND 200) AS invalid_display_name,
 (SELECT count(*) FROM (SELECT email FROM users GROUP BY email HAVING count(*)>1) q) AS duplicate_email_groups,
 (SELECT count(*) FROM google g WHERE NOT EXISTS (SELECT 1 FROM users u WHERE u.id=g.user_id)) AS orphan_google_links,
 (SELECT count(*) FROM google WHERE provider_subject IS NULL OR provider_subject<>btrim(provider_subject)
    OR length(provider_subject) NOT BETWEEN 1 AND 255) AS invalid_google_subjects,
 (SELECT count(*) FROM (SELECT provider_subject FROM google GROUP BY provider_subject HAVING count(*)>1) q) AS duplicate_google_subject_groups;
ROLLBACK;
))='$argon2id
               THEN 'candidate'
             ELSE 'unsupported' END AS password_kind
 FROM public.app_users
), google AS (
 SELECT user_id::text AS user_id, provider_subject
 FROM public.auth_identities WHERE provider='google'
)
SELECT
 (SELECT count(*) FROM users) AS accounts,
 (SELECT count(*) FROM google) AS google_links,
 (SELECT count(*) FROM users WHERE password_kind='unsupported') AS unsupported_passwords,
 (SELECT count(*) FROM users WHERE password_kind='malformed') AS malformed_passwords,
 (SELECT count(*) FROM users WHERE password_kind='candidate') AS candidate_passwords,
 (SELECT count(*) FROM users WHERE password_kind='absent') AS absent_passwords,
 (SELECT count(*) FROM users u WHERE password_kind IN ('absent','unsupported','malformed')
    AND NOT EXISTS (SELECT 1 FROM google g WHERE g.user_id=u.id)) AS accounts_without_candidate_login,
 (SELECT count(*) FROM users WHERE active IS DISTINCT FROM TRUE) AS inactive_accounts,
 (SELECT count(*) FROM users WHERE id !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$') AS invalid_uuid,
 (SELECT count(*) FROM users WHERE email IS NULL OR email<>lower(email)
    OR email<>btrim(email) OR length(email) NOT BETWEEN 1 AND 320 OR position('@' in email)=0) AS invalid_email,
 (SELECT count(*) FROM users WHERE display_name IS NULL OR display_name<>btrim(display_name)
    OR length(display_name) NOT BETWEEN 1 AND 200) AS invalid_display_name,
 (SELECT count(*) FROM (SELECT email FROM users GROUP BY email HAVING count(*)>1) q) AS duplicate_email_groups,
 (SELECT count(*) FROM google g WHERE NOT EXISTS (SELECT 1 FROM users u WHERE u.id=g.user_id)) AS orphan_google_links,
 (SELECT count(*) FROM google WHERE provider_subject IS NULL OR provider_subject<>btrim(provider_subject)
    OR length(provider_subject) NOT BETWEEN 1 AND 255) AS invalid_google_subjects,
 (SELECT count(*) FROM (SELECT provider_subject FROM google GROUP BY provider_subject HAVING count(*)>1) q) AS duplicate_google_subject_groups;
ROLLBACK;
 OR left(password_hash,length('pbkdf2_sha256
               THEN 'candidate'
             ELSE 'unsupported' END AS password_kind
 FROM public.app_users
), google AS (
 SELECT user_id::text AS user_id, provider_subject
 FROM public.auth_identities WHERE provider='google'
)
SELECT
 (SELECT count(*) FROM users) AS accounts,
 (SELECT count(*) FROM google) AS google_links,
 (SELECT count(*) FROM users WHERE password_kind='unsupported') AS unsupported_passwords,
 (SELECT count(*) FROM users WHERE password_kind='malformed') AS malformed_passwords,
 (SELECT count(*) FROM users WHERE password_kind='candidate') AS candidate_passwords,
 (SELECT count(*) FROM users WHERE password_kind='absent') AS absent_passwords,
 (SELECT count(*) FROM users u WHERE password_kind IN ('absent','unsupported','malformed')
    AND NOT EXISTS (SELECT 1 FROM google g WHERE g.user_id=u.id)) AS accounts_without_candidate_login,
 (SELECT count(*) FROM users WHERE active IS DISTINCT FROM TRUE) AS inactive_accounts,
 (SELECT count(*) FROM users WHERE id !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$') AS invalid_uuid,
 (SELECT count(*) FROM users WHERE email IS NULL OR email<>lower(email)
    OR email<>btrim(email) OR length(email) NOT BETWEEN 1 AND 320 OR position('@' in email)=0) AS invalid_email,
 (SELECT count(*) FROM users WHERE display_name IS NULL OR display_name<>btrim(display_name)
    OR length(display_name) NOT BETWEEN 1 AND 200) AS invalid_display_name,
 (SELECT count(*) FROM (SELECT email FROM users GROUP BY email HAVING count(*)>1) q) AS duplicate_email_groups,
 (SELECT count(*) FROM google g WHERE NOT EXISTS (SELECT 1 FROM users u WHERE u.id=g.user_id)) AS orphan_google_links,
 (SELECT count(*) FROM google WHERE provider_subject IS NULL OR provider_subject<>btrim(provider_subject)
    OR length(provider_subject) NOT BETWEEN 1 AND 255) AS invalid_google_subjects,
 (SELECT count(*) FROM (SELECT provider_subject FROM google GROUP BY provider_subject HAVING count(*)>1) q) AS duplicate_google_subject_groups;
ROLLBACK;
))='pbkdf2_sha256
               THEN 'candidate'
             ELSE 'unsupported' END AS password_kind
 FROM public.app_users
), google AS (
 SELECT user_id::text AS user_id, provider_subject
 FROM public.auth_identities WHERE provider='google'
)
SELECT
 (SELECT count(*) FROM users) AS accounts,
 (SELECT count(*) FROM google) AS google_links,
 (SELECT count(*) FROM users WHERE password_kind='unsupported') AS unsupported_passwords,
 (SELECT count(*) FROM users WHERE password_kind='malformed') AS malformed_passwords,
 (SELECT count(*) FROM users WHERE password_kind='candidate') AS candidate_passwords,
 (SELECT count(*) FROM users WHERE password_kind='absent') AS absent_passwords,
 (SELECT count(*) FROM users u WHERE password_kind IN ('absent','unsupported','malformed')
    AND NOT EXISTS (SELECT 1 FROM google g WHERE g.user_id=u.id)) AS accounts_without_candidate_login,
 (SELECT count(*) FROM users WHERE active IS DISTINCT FROM TRUE) AS inactive_accounts,
 (SELECT count(*) FROM users WHERE id !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$') AS invalid_uuid,
 (SELECT count(*) FROM users WHERE email IS NULL OR email<>lower(email)
    OR email<>btrim(email) OR length(email) NOT BETWEEN 1 AND 320 OR position('@' in email)=0) AS invalid_email,
 (SELECT count(*) FROM users WHERE display_name IS NULL OR display_name<>btrim(display_name)
    OR length(display_name) NOT BETWEEN 1 AND 200) AS invalid_display_name,
 (SELECT count(*) FROM (SELECT email FROM users GROUP BY email HAVING count(*)>1) q) AS duplicate_email_groups,
 (SELECT count(*) FROM google g WHERE NOT EXISTS (SELECT 1 FROM users u WHERE u.id=g.user_id)) AS orphan_google_links,
 (SELECT count(*) FROM google WHERE provider_subject IS NULL OR provider_subject<>btrim(provider_subject)
    OR length(provider_subject) NOT BETWEEN 1 AND 255) AS invalid_google_subjects,
 (SELECT count(*) FROM (SELECT provider_subject FROM google GROUP BY provider_subject HAVING count(*)>1) q) AS duplicate_google_subject_groups;
ROLLBACK;

               THEN 'candidate'
             ELSE 'unsupported' END AS password_kind
 FROM public.app_users
), google AS (
 SELECT user_id::text AS user_id, provider_subject
 FROM public.auth_identities WHERE provider='google'
)
SELECT
 (SELECT count(*) FROM users) AS accounts,
 (SELECT count(*) FROM google) AS google_links,
 (SELECT count(*) FROM users WHERE password_kind='unsupported') AS unsupported_passwords,
 (SELECT count(*) FROM users WHERE password_kind='malformed') AS malformed_passwords,
 (SELECT count(*) FROM users WHERE password_kind='candidate') AS candidate_passwords,
 (SELECT count(*) FROM users WHERE password_kind='absent') AS absent_passwords,
 (SELECT count(*) FROM users u WHERE password_kind IN ('absent','unsupported','malformed')
    AND NOT EXISTS (SELECT 1 FROM google g WHERE g.user_id=u.id)) AS accounts_without_candidate_login,
 (SELECT count(*) FROM users WHERE active IS DISTINCT FROM TRUE) AS inactive_accounts,
 (SELECT count(*) FROM users WHERE id !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$') AS invalid_uuid,
 (SELECT count(*) FROM users WHERE email IS NULL OR email<>lower(email)
    OR email<>btrim(email) OR length(email) NOT BETWEEN 1 AND 320 OR position('@' in email)=0) AS invalid_email,
 (SELECT count(*) FROM users WHERE display_name IS NULL OR display_name<>btrim(display_name)
    OR length(display_name) NOT BETWEEN 1 AND 200) AS invalid_display_name,
 (SELECT count(*) FROM (SELECT email FROM users GROUP BY email HAVING count(*)>1) q) AS duplicate_email_groups,
 (SELECT count(*) FROM google g WHERE NOT EXISTS (SELECT 1 FROM users u WHERE u.id=g.user_id)) AS orphan_google_links,
 (SELECT count(*) FROM google WHERE provider_subject IS NULL OR provider_subject<>btrim(provider_subject)
    OR length(provider_subject) NOT BETWEEN 1 AND 255) AS invalid_google_subjects,
 (SELECT count(*) FROM (SELECT provider_subject FROM google GROUP BY provider_subject HAVING count(*)>1) q) AS duplicate_google_subject_groups;
ROLLBACK;
