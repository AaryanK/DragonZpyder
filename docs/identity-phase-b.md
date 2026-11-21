# Phase B — Canonical user identity reconciliation (non-executing)

The shared identity authority will live in DragonZpyder API, not in another Railway service. This phase introduces a **fail-closed import validator** and **review-only SQL schema**; it does not yet implement login, JWT issuance, or database migration.

Inputs: a database snapshot of Operly `app_users`, `auth_identities`, and `external_identities`. Use a protected, offline backend export; no passwords, session secrets or OAuth tokens enter the validator. Match Google identities by provider subject, not email. Existing verified Discord links remain channel bindings, **not** login grants unless a separate verified Discord OAuth login exchange is implemented.

Guards: unique Operly ID, no orphaned links, no cross-user provider subject collisions, no duplicate identity records and no unverified external links. Any failure stops the entire import and requires operator review. The SQL schema remains inert until an explicitly approved staged database migration; pending users cannot authenticate.

Next stage: actual audited identity database and migration tooling; OAuth2/OIDC issuer using proven libraries with PKCE, signed tokens, JWKS/key rotation, revocation, first-party sessions and account recovery; then Operly audience-specific identity verification and mapping, staged cutover and rollback. These are not satisfied by this PR.

Dependency: [Phase A password parity](https://github.com/AaryanK/DragonZpyder/pull/73).
