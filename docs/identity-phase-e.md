# Phase E — Authenticated browser sessions and OAuth grants (core only)

**Not yet a live login system. No API endpoint uses these functions.**

## Added
- Pending-only client registry schema, 90-second one-time authorization codes, exact HTTPS redirect URI binding, S256 PKCE and audience/scope checks.
- Opaque 7-day first-party identity browser sessions with hashed secrets and hashed CSRF tokens, revocation and account-status verification on every use.
- Separate HMAC grant key `DRAGONZPYDER_IDENTITY_GRANT_HASH_KEY` (32+ bytes); no raw codes or session cookies stored in the DB.
- Unit tests using synthetic account IDs and fake DB connections. Real PostgreSQL concurrency tests remain required.

## Wire into existing DragonZpyder API only after
1. Account migration in isolated staging environment, unique constraints and source-owned identity proof are verified; remove the Phase D hard activation fence only in a separately reviewed migration.
2. Password/Google/Discord authenticated login endpoints and server-set `Secure`, `HttpOnly`, host-only, appropriate SameSite cookies. Google/Discord login MUST validate ID/OAuth state+nonce and provider subject; Discord channel linking alone cannot authorize login.
3. Implement browser `/authorize` with login session, CSRF+consent checks; server-side `/token` with PKCE exchange, bounded audiences, refresh rotation with replay/family revocation, and token binding to proper client.
4. Register `operly-web` and `dragonzpyder-web` clients with exact redirect URIs and least-privilege scopes. Never trust a browser-supplied account ID, redirect URL, audience or scope without server registry validation.
5. Implement refresh-grant storage, key-rotation overlap, logout/revocation propagation, admin identity governance and discovery metadata *only after* the full endpoints exist.
6. Configure signed public JWKS and pin trust in Operly. Implement Operly OIDC code callback and first-party Operly session issuance, preserving membership checks. Do not share DragonZpyder cookies across domains.
7. Run live PostgreSQL serializability/race tests, security gates and forced rollbacks before canary. Do not interpret synthetic tests as proof of production behavior.

No extra Railway service is necessary; existing DragonZpyder API is the intended host.

This phase adds **server-side primitives**. In particular, `authorize_code` must be called only by a *trusted authenticated interactive session*, not directly from an exposed endpoint. The SQL files are review-only and not auto-applied.
