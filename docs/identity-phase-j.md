# Phase J — Nonce-bound ID tokens + refresh exchange (feature-gated)

DragonZpyder's **existing API** remains the intended identity authority. No separate Railway service is introduced.

## Implemented in this phase
- An `openid` authorization request **requires** a 24–128 character nonce. The nonce is persisted with the 90-second single-use code and never accepted as a `/token` parameter. Missing nonce is denied before code issuance. `offline_access` requires `openid`.
- Code exchange issues a five-minute RS256 **access token** for the resource audience and, only when `openid` is granted, an **ID token** for the client ID. The ID token binds the authorization nonce and contains an `at_hash` over the paired access token.
- When `offline_access` is granted, an opaque refresh token is inserted **in the same PostgreSQL transaction** that consumes the authorization code. A refresh-insert failure rolls back consumption.
- `POST /identity/v1/token` now distinguishes strictly shaped, form-encoded authorization-code and refresh-token exchanges. Refresh rotation returns a new access token and refresh token; it does **not** invent an ID token without a saved nonce.
- Existing HTTP and grant tests adapted; new cryptographic claim, audience, nonce, replay-rejection, refresh and transaction contract tests. GitHub Actions now explicitly runs every identity contract test (previously the legacy API workflow omitted them). A separate **disposable PostgreSQL 16** acceptance job verifies pending-account rejection, nonce-bound code exchange, single-use redemption, and concurrent refresh replay revoking the whole family.
- Routes retain `DRAGONZPYDER_IDENTITY_HTTP_ENABLED=0` default and the separate production block. Imported accounts are still pending-only by Phase D schema, so no real user can log in through this implementation.

## Known missing pieces — not yet compliant production OIDC
1. **Interactive GET authorization flow and consent**: the current /authorize route is a server-validated POST bridge, not a standard browser authorization endpoint. Do not publish OIDC discovery metadata that advertises a nonexistent GET flow.
2. **Frontend clients**: Operly and DragonZpyder must implement code+PKCE launch, state validation, ID-token signature/audience/nonce checks, local sessions and logout.
3. **Real activation and identity migration**: stage restored accounts and verified links; run a full restored-data migration rehearsal and production-like contention tests beyond the disposable PostgreSQL acceptance checks; approve a separate activation migration. No live data imported here.
4. **Session safety and provider review**: Google/Discord callback verification on real registered apps, account recovery, rate-limit defenses, user consent, anti-login-CSRF, account disable propagation.
5. **Refresh grant hardening**: absolute lifetime limits, client/device binding where possible, durable revocation and signing-key rotation/multiple JWKS keys; refresh flow is not yet interoperability-tested with standard OIDC client libraries.
6. **Complete token security and infrastructure**: external security review, separate auth DB role and signing key isolation, restore rehearsal, production canary/rollback.
7. **Operly**: validate pinned JWKS and exact issuer+subject and preserve TenantMember authorization; earlier Operly verifier PRs remain unmerged.
8. **Audit earlier stacked PRs** before enabling auth; passing synthetic CI does not establish a secure identity provider.

This is a **draft, non-production** phase built on Phase I [PR #86](https://github.com/AaryanK/DragonZpyder/pull/86).
