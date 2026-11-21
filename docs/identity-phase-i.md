# Phase I — OAuth refresh-grant lifecycle (draft)

This change adds an **internal** refresh-token lifecycle to the existing DragonZpyder API package. It does **not** make DragonZpyder a conformant OpenID Connect provider yet.

## Implemented
- 30-day maximum opaque, HMAC-hashed refresh token; dedicated DB-backed grant family.
- Re-registers and checks enabled OAuth client, exact redirect, authorized scopes/audience and current active account on issuance and rotation.
- Transactional single-use rotation serialized by PostgreSQL transaction-scoped family advisory lock; consumed token replay revokes the family and commits revocation before signaling denial.
- Explicit family revocation and synthetic negative tests; no secrets emitted to logging or tools.
- Existing `identity_refresh_grants` staging-only table from Phase E, no new Railway service.

## Must remain disabled
- Refresh is **not yet wired to the HTTP token endpoint**; the current code-grant response remains short-lived access tokens only.
- No first-party ID token, nonce bound to code, userinfo, discovery document, OIDC consent UI, or real client/browser callback is implemented.
- Phase D identity accounts remain pending-only by schema. No real accounts or provider secrets are migrated.
- Real PostgreSQL concurrent replay testing, absolute maximum family lifetime and key rotation must be completed before grant issuance.

## Release gates
- Integrate refresh with authorization-code exchange in a single transactional grant issuance flow.
- Bind OIDC nonce to each auth code, sign ID tokens to client_id, publish OIDC discovery only after all advertised operations are functional.
- Federated Operly OIDC callback with session issuance and current workspace authorization, both web clients, live Postgres tests and security review.
- Canary/rollback and session revocation across both applications; no production flags changed in this phase.

Stacked on Phase H PR #84. Do not merge out of order.
