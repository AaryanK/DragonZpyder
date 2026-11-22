-- Staged identity extension for users who NEVER had Operly accounts.
-- REVIEW / APPLY BY OPERATOR ONLY. Never run on API startup.
-- Existing imported users stay locked pending a separate audited activation.
ALTER TABLE identity_accounts
    ADD COLUMN IF NOT EXISTS identity_origin VARCHAR(32) NOT NULL DEFAULT 'operly_import';
ALTER TABLE identity_accounts
    ALTER COLUMN source_operly_user_id DROP NOT NULL;
ALTER TABLE identity_accounts
    DROP CONSTRAINT IF EXISTS identity_account_pending_or_disabled;
ALTER TABLE identity_accounts
    ADD CONSTRAINT identity_import_not_automatically_active
      CHECK (identity_origin <> 'operly_import' OR status <> 'active');
ALTER TABLE identity_accounts
    ADD CONSTRAINT identity_native_origin_valid
      CHECK (identity_origin IN ('operly_import', 'native_google'));
ALTER TABLE identity_accounts
    ADD CONSTRAINT identity_source_link_consistency
      CHECK ((identity_origin = 'operly_import' AND source_operly_user_id IS NOT NULL)
         OR (identity_origin = 'native_google' AND source_operly_user_id IS NULL));

-- Google subject uniqueness already exists in identity_provider_links.
-- Google/email collision NEVER merges a pre-existing Operly account.
-- A second, independently audited path is required for email/password signup,
-- email verification, forgot-password and account-delete lifecycle.
