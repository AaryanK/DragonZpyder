# Shared DragonZpyder / Operly identity — staged migration contract

## Ownership
DragonZpyder API becomes the **single identity issuer**, Operly an OIDC client and the continuing authority for its workspace membership and business records. Today DragonZpyder Web proxies Operly account endpoints, while the optional Personal Core verifies OIDC access tokens; neither is an independently functioning OIDC identity issuer.

## User identities
- Preserve Operly `app_users.id` and every workspace foreign key. Add a unique `(issuer, subject) -> operly_user_id` mapping after the identity issuer exists.
- Map verified Google identities by provider **subject**, never matching or auto-merging users by email alone. Preserve validated Discord external identities without silently upgrading a Discord link to a login method.
- Quarantine conflicting, missing or unverified identity bindings; require explicit proof/review before granting login. Export and import under controlled staging backend only.
- Port Operly Argon2id and PBKDF2 verification for password login without exposing plaintext. Upgrade legacy hashes only after successful sign-in.

## Required before enabling production
1. Staging database restored from an approved, scrubbed backup and verified row/constraint counts. No live data or secret export in this PR.
2. DragonZpyder API must implement OIDC issuer discovery/JWKS, signed tokens, Authorization Code + PKCE, separate first-party sessions, logout, revocation, refresh rotation, rate limits and recovery. Keep auth DB roles, signing keys and secrets isolated from agent workloads.
3. Operly validates token signature, issuer, audience, expiry and exact mapped subject, then *independently* resolves workspace role and permissions. No user-supplied ID headers, cookies shared across domains or ID tokens accepted as API bearer access tokens.
4. Existing Operly sessions remain valid while users progressively switch login. Implement a no-account-duplication migration bridge and rollback before redirecting either web app.
5. Migrate personal connector metadata and secrets separately: verified owner, backend-only decrypt/reencrypt, explicit OAuth scope review; require reconnect where provider credentials are not transferable.
6. Canary and test both websites, Google/Discord linking, accounts with passwords, expiry/revocation, workspace isolation, sandbox/agent secret isolation and failed login abuse before broader rollout.
7. Back up and rehearse rollback; only disable legacy authentication after measured success and reconciliation.

## Phase A delivered
A pure Python compatibility module under `api/identity/passwords.py`, bundled Operly password-policy corpus and isolated tests. **No auth endpoints, provider secrets, account rows or production flags change.**
