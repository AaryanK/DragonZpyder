# Phase G — Password login from migrated accounts (still disabled)

## Implemented
- Password credential verification against a DragonZpyder identity DB row with an existing Operly user ID as immutable `sub`, including Argon2id and legacy PBKDF2-to-Argon2id upgrade.
- Central database-based per-account attempt throttle (8 attempts per 15-minute window across replicas), hashed identifiers (not plaintext emails).
- Password verification offloaded from event loop; login never trusts client-provided user IDs.
- Host-only Secure HttpOnly identity-session cookie and separate Secure CSRF cookie; logout verifies server-side session CSRF and revokes the active session.
- `POST /identity/v1/password/login` and `POST /identity/v1/logout` mounted but **not available** unless the identity HTTP gate is explicitly enabled. Production has a separate approval gate.
- Synthetic tests, no live database reads or secret handling.

## Still blocked by design
Phase D schema prevents account status `active`. Real login cannot succeed until an approved post-migration activation policy changes that constraint, and production flags remain off. No Google or Discord login was added here.

## Mandatory before enabling
- Security review of password reset, email verification policy, login enumeration and response timing, source-user deactivation synchronization, abuse throttling by IP/device and anti-bot controls.
- Run actual PostgreSQL tests for atomic throttling, account disable, password-upgrade contention and session creation/revocation; validate browser SameSite and CSRF behavior against real endpoints.
- Provider-subject verification and account linking for Google/Discord; add signup/recovery/MFA and controlled consent UI.
- Refresh-token rotation, revocation, OIDC discovery/id_token, reliable JWKS rollover; require sessions and token issuance to use separately audited authentication.
- Operly OIDC callback and session establishment plus tenant/member authorization checks; canary/rollback rehearsal and real imported-user testing.
- Import all pre-existing account records from an authorized Operly backup only after backups, collision resolution and a staged deployment plan.
