-- Manual ONLY after identity reconciliation, provider proof and rollback review.
-- Must be executed with a migration-only DB role, never on startup and
-- never with the user-facing API's database credentials.
-- This removes the *temporary* imported-account activation block. It does not
-- automatically activate ANY imported accounts.
ALTER TABLE identity_accounts
    DROP CONSTRAINT IF EXISTS identity_import_not_automatically_active;

-- Keep imported subjects and source IDs one-to-one. Existing Operly-linked
-- accounts remain pending until verified and explicitly updated by operators.
-- RLS/GRANT must exclude the web/API role from status changes and from this
-- privileged migration.
SELECT count(*) AS remaining_pending_imports
FROM identity_accounts
WHERE identity_origin='operly_import' AND status='pending';
