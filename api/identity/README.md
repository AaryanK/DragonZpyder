# api/identity

First-party identity HTTP handlers, auth/session/token primitives, account migration and SQL schemas.

Read [repository instructions](../../AGENTS.md) and [codebase navigation](../../CODEBASE.md). See the [implementation guide](../../docs/codebase/IMPLEMENTATION.md) and [complete baseline file inventory](../../docs/codebase/FILE_INDEX.md). This is a navigation note, not proof that a feature is enabled or deployed.

| Local file | Navigation | Evidence |
| --- | --- | --- |
| [`MOBILE_OAUTH_RELEASE.md`](MOBILE_OAUTH_RELEASE.md) | Documentation: MOBILE OAUTH RELEASE; check date and canonical status. | Indexed |
| [`__init__.py`](__init__.py) | Navigation hint:   init  ; source behavior not independently reviewed. | Indexed |
| [`active_recovery_http.py`](active_recovery_http.py) | Navigation hint: active recovery http; source behavior not independently reviewed. | Indexed |
| [`authorize_ui.css`](authorize_ui.css) | Stylesheet: authorize ui; inspect selectors and importing page. | Indexed |
| [`authorize_ui.js`](authorize_ui.js) | Navigation hint: authorize ui; source behavior not independently reviewed. | Indexed |
| [`browser_authorize.py`](browser_authorize.py) | Browser authorization and consent UI, same-origin assets and Google sign-in page. | Reviewed |
| [`common_passwords.txt`](common_passwords.txt) | Navigation hint: common passwords; source behavior not independently reviewed. | Indexed |
| [`consent.py`](consent.py) | Session-bound single-use consent interaction for the exact registered OAuth request fields. | Reviewed |
| [`exchange.py`](exchange.py) | Atomic authorization-code and refresh exchange with OIDC nonce; consumes code and creates refresh in one transaction. | Reviewed |
| [`grants.py`](grants.py) | Server-side authorization-code and S256 PKCE grant validation and redemption. | Reviewed |
| [`http_bridge.py`](http_bridge.py) | Identity database/gate helpers, POST authorization and token HTTP bridge. | Reviewed |
| [`importer.py`](importer.py) | Strict authorized staging account/provider snapshot preparation and all-or-nothing import; no API or agent entrypoint. | Reviewed |
| [`issuer_google_ui.js`](issuer_google_ui.js) | Navigation hint: issuer google ui; source behavior not independently reviewed. | Indexed |
| [`login_http.py`](login_http.py) | Password login, logout, native profile lookup/update HTTP adapters. | Reviewed |
| [`mobile_provider.py`](mobile_provider.py) | Native browser-provider start/callback/redeem with PKCE and ticket binding; provider capabilities. | Reviewed |
| [`native_recovery_http.py`](native_recovery_http.py) | Navigation hint: native recovery http; source behavior not independently reviewed. | Indexed |
| [`native_signup.py`](native_signup.py) | Explicit verified Google signup, without email-based linking of Operly identities. | Reviewed |
| [`offline_transfer.py`](offline_transfer.py) | Operator-only sealed encrypted packages across isolated production DB networks; private file handling and migration-role checks. | Reviewed |
| [`password_login.py`](password_login.py) | Database-backed password login, indistinguishable failures, shared PostgreSQL rate limiting and PBKDF2-to-Argon2 upgrade. | Reviewed |
| [`passwords.py`](passwords.py) | Pure email normalization, password policy, legacy PBKDF2 compatibility and Argon2id hash/verification. | Reviewed |
| [`pending_proof_http.py`](pending_proof_http.py) | Navigation hint: pending proof http; source behavior not independently reviewed. | Indexed |
| [`pending_proofs.py`](pending_proofs.py) | Checks migrated pending identity password or Google proof without granting session or activation. | Reviewed |
| [`pending_reconciliation.py`](pending_reconciliation.py) | Operator-only read-only source/target reconciliation with keyed full-field snapshot receipts, not just counts. | Reviewed |
| [`production_import.py`](production_import.py) | Operator-only scoped pending production identity import with independently approved inventory and count validation. | Reviewed |
| [`provider_challenges.py`](provider_challenges.py) | Creates and consumes one-time browser-bound provider challenge state, binding and nonce. | Reviewed |
| [`provider_http.py`](provider_http.py) | Browser Google/Discord challenge initiation and completion; explicit Google signup path; verifies state/nonce/binding before session. | Reviewed |
| [`providers.py`](providers.py) | Validates Google ID tokens and Discord OAuth code exchange, looks up verified provider subject, never merges accounts by email. | Reviewed |
| [`reconciliation.py`](reconciliation.py) | Fail-closed validation and reconciliation of authorized Operly identity exports; no database mutation or authentication. | Reviewed |
| [`recovery_delta.py`](recovery_delta.py) | Plans and applies reviewed pending recovery additions; requires source-authority handoff/freeze before writes. | Reviewed |
| [`refresh.py`](refresh.py) | Opaque hashed single-use refresh tokens, atomic rotation and family replay revocation. | Reviewed |
| [`relying_party_status.py`](relying_party_status.py) | Navigation hint: relying party status; source behavior not independently reviewed. | Indexed |
| [`router.py`](router.py) | JWKS and OIDC discovery routes. | Reviewed |
| [`schema_active_recovery_review.sql`](schema_active_recovery_review.sql) | SQL named for schema active recovery review; inspect statements, transaction requirements and target database before use. | Indexed |
| [`schema_bootstrap_manual.sql`](schema_bootstrap_manual.sql) | SQL named for schema bootstrap manual; inspect statements, transaction requirements and target database before use. | Indexed |
| [`schema_consent_staging.sql`](schema_consent_staging.sql) | SQL named for schema consent staging; inspect statements, transaction requirements and target database before use. | Indexed |
| [`schema_export_role_manual.sql`](schema_export_role_manual.sql) | SQL named for schema export role manual; inspect statements, transaction requirements and target database before use. | Indexed |
| [`schema_first_party_clients_staging.sql`](schema_first_party_clients_staging.sql) | SQL named for schema first party clients staging; inspect statements, transaction requirements and target database before use. | Indexed |
| [`schema_import_activation_review.sql`](schema_import_activation_review.sql) | SQL named for schema import activation review; inspect statements, transaction requirements and target database before use. | Indexed |
| [`schema_login_staging.sql`](schema_login_staging.sql) | SQL named for schema login staging; inspect statements, transaction requirements and target database before use. | Indexed |
| [`schema_migration_role_manual.sql`](schema_migration_role_manual.sql) | SQL named for schema migration role manual; inspect statements, transaction requirements and target database before use. | Indexed |
| [`schema_mobile_provider_manual.sql`](schema_mobile_provider_manual.sql) | SQL named for schema mobile provider manual; inspect statements, transaction requirements and target database before use. | Indexed |
| [`schema_native_google_signup.sql`](schema_native_google_signup.sql) | SQL named for schema native google signup; inspect statements, transaction requirements and target database before use. | Indexed |
| [`schema_native_pending_recovery_review.sql`](schema_native_pending_recovery_review.sql) | SQL named for schema native pending recovery review; inspect statements, transaction requirements and target database before use. | Indexed |
| [`schema_oauth_staging.sql`](schema_oauth_staging.sql) | SQL named for schema oauth staging; inspect statements, transaction requirements and target database before use. | Indexed |
| [`schema_provider_challenge_staging.sql`](schema_provider_challenge_staging.sql) | SQL named for schema provider challenge staging; inspect statements, transaction requirements and target database before use. | Indexed |
| [`schema_recovery_sync_role_manual.sql`](schema_recovery_sync_role_manual.sql) | SQL named for schema recovery sync role manual; inspect statements, transaction requirements and target database before use. | Indexed |
| [`schema_role_manual.sql`](schema_role_manual.sql) | SQL named for schema role manual; inspect statements, transaction requirements and target database before use. | Indexed |
| [`schema_sessions_staging.sql`](schema_sessions_staging.sql) | SQL named for schema sessions staging; inspect statements, transaction requirements and target database before use. | Indexed |
| [`schema_staging.sql`](schema_staging.sql) | SQL named for schema staging; inspect statements, transaction requirements and target database before use. | Indexed |
| [`sessions.py`](sessions.py) | Opaque host-only browser sessions, active-account checks, CSRF validation and revocation. | Reviewed |
| [`source_inventory_manual.sql`](source_inventory_manual.sql) | SQL named for source inventory manual; inspect statements, transaction requirements and target database before use. | Indexed |
| [`source_recovery_inventory_manual.sql`](source_recovery_inventory_manual.sql) | SQL named for source recovery inventory manual; inspect statements, transaction requirements and target database before use. | Indexed |
| [`tokens.py`](tokens.py) | RS256 SigningIdentity, PKCE helpers and issuer/token signing primitives; private signing keys never reach agent context. | Reviewed |
