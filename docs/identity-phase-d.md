# Phase D: controlled identity storage and import

**Status:** code-only foundation, no production migration, SSO, login, OAuth or token issuance enabled.

The DragonZpyder API continues to host the future identity system; this does not create a new Railway service.

## Implemented
- `api/identity/schema_staging.sql` models accounts with source Operly ID, email, password hash, display name, verification/active status and provider links.
- A database check disallows `status='active'`. Staged data cannot authenticate until an explicitly reviewed later schema change.
- `prepare_snapshot` validates each source account and calls Phase B's identity collision detection. Canonical `sub` remains equal to the existing immutable Operly user ID, avoiding workspace-key rewrites.
- `import_into_staging` requires `approved=True` and `DRAGONZPYDER_IDENTITY_STAGING_IMPORT=1`, locks imports, rejects nonempty destinations, uses parameterized SQL, and inserts accounts/links in one transaction with count reconciliation.
- No API route, agent tool, automated scheduled job or startup migration invokes the importer.

## Operator-only staging procedure (not executed)
1. Verify the Operly and DragonZpyder deployment references and back up production.
2. Restore an authorized Operly backup into an isolated staging DB. Extract `app_users`, `auth_identities` and `external_identities` through an access-controlled offline pipeline. Avoid exporting sessions, OAuth refresh tokens or unrelated business records.
3. Convert verification timestamps to timezone-aware datetimes. Run `prepare_snapshot`; stop if any identity collision or unsupported hash appears.
4. Apply `schema_staging.sql` only to a clean, backed-up, isolated PostgreSQL staging DB. Use least-privilege migration DB credentials.
5. Run the approved importer in an isolated operator process and verify transaction counts, pending-only status, Google identity ownership and Discord links.
6. Rehearse rollback and document the count and identity results, without dumping PII or secret material to logs.

## Before any real account cutover
- Implement audited auth DB storage and browser session store, OAuth2 Authorization Code + PKCE, state/nonce and CSRF, revocation, refresh rotation, account recovery, and secure Google/Discord login/linking.
- Harden token issuer/JWKS with key rotation, permitted audiences/client registry and isolated signing-key access.
- Implement Operly JWKS fetch with pinned issuer and exact subject mapping in the public request path. Preserve workspace Kernel checks; retain existing Operly sessions through canary.
- Migrate personal connector vault separately and validate provider-specific token-transfer feasibility.
- Add live PostgreSQL integration tests for atomic import failure/retry and backup/restore; Phase D's fake DB tests alone are insufficient for production readiness.

Dependency: Phase C [DragonZpyder #78](https://github.com/AaryanK/DragonZpyder/pull/78). Do not merge or deploy this as production identity without completing the above.
