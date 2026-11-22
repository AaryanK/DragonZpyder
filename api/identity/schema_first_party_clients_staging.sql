-- OPERATOR-ONLY exact OAuth client registration, not an automatic startup migration.
-- Requires the separate dedicated identity DB and schema_oauth_staging.sql.
-- Adds neither an account nor an enabled client.
BEGIN;
SELECT pg_advisory_xact_lock(739110212);
DO $$
BEGIN
    IF EXISTS (
      SELECT 1 FROM identity_oauth_clients
      WHERE (client_id = 'operly-web' AND (
         redirect_uri <> 'https://operly.dragonzpyder.xyz/api/auth/dragonzpyder/callback'
         OR audience <> 'operly-api'
         OR allowed_scope <> 'openid operly:access'))
      OR (client_id = 'dragonzpyder-web' AND (
         redirect_uri <> 'https://dragonzpyder.xyz/api/auth/dragonzpyder/web/callback'
         OR audience <> 'operly-api'
         OR allowed_scope <> 'openid operly:access'))
    ) THEN
      RAISE EXCEPTION 'Existing first-party client configuration differs from reviewed registration';
    END IF;
END $$;
INSERT INTO identity_oauth_clients
  (client_id, redirect_uri, audience, allowed_scope, enabled)
VALUES
  ('operly-web',
   'https://operly.dragonzpyder.xyz/api/auth/dragonzpyder/callback',
   'operly-api', 'openid operly:access', FALSE),
  ('dragonzpyder-web',
   'https://dragonzpyder.xyz/api/auth/dragonzpyder/web/callback',
   'operly-api', 'openid operly:access', FALSE)
ON CONFLICT (client_id) DO NOTHING;
COMMIT;
