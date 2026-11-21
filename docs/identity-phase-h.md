# Phase H — Google and Discord account login proof

**Feature-gated and disabled in production.** Adds no separate Railway service.

The existing DragonZpyder FastAPI includes:

- `POST /identity/v1/provider/google/start` produces a server-recorded 5-minute state and Google nonce, plus a host-only Secure HttpOnly browser-bound challenge cookie.
- `POST /identity/v1/provider/google/complete` consumes state once and verifies Google's signed ID token, configured audience/issuer, verified email flag, expiry and nonce. Only exact Google provider subjects already marked login-eligible are accepted.
- `POST /identity/v1/provider/discord/start` returns a Discord OAuth authorize URL with unique state and a browser-binding cookie. The callback `GET /identity/v1/provider/discord/callback` consumes the state, exchanges the code server-to-server using the Discord app secret and reads Discord `/users/@me` for the immutable user ID.
- Both providers resolve against `identity_provider_links` using exact `provider` + `provider_subject`, `source='auth'`, `login_eligible=TRUE` and active source+canonical account status. **No email-based account creation/merge** or privilege elevation from Discord `external` links.
- On successful proof, creates an existing first-party opaque browser session. No provider tokens are stored as user connector credentials, printed or provided to the agent.

## Required prerequisites and constraints

1. Feature flags are disabled; Phase D's SQL hard-pins all imported accounts to pending until a separately reviewed migration. Routes are not usable for real migrated accounts yet.
2. The identity origin and OAuth provider client IDs/secrets/redirect URI must be configured in protected server-only environment. No credentials have been copied from Operly.
3. Google login should run on the identity origin with credential ID token whose nonce equals the server challenge; do not reuse Operly's Google client ID unless explicitly permitted. Discord requires OAuth `identify` and an exact registered callback.
4. A verified Discord channel link from Operly is **not automatically** an authenticated Discord login. Require separate user proof before upgrading login eligibility; no automatic email merge.
5. Before production, implement OIDC client UX on both sites, refresh-token rotation/family revocation, consent and ID token, account recovery, approved user activation, actual PostgreSQL transaction/race tests, anti-abuse per IP and device, JWKS key rollover, backup, migration canary and rollback.
6. Legacy Operly session acceptance and local Operly TenantMember checks remain unchanged.

This is the provider-verification layer, NOT completed cross-site SSO.
