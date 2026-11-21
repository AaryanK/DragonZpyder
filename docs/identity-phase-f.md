# Phase F — HTTP OAuth authorization-code bridge (disabled by default)

This is an integration increment, **not a production-ready OAuth/OIDC identity provider**.

## New endpoints on existing DragonZpyder API
- `POST /identity/v1/authorize`: Requires an already-authenticated DragonZpyder identity browser session, a matching server-side CSRF secret, same-origin Origin header, registered OAuth client and exact redirect URI, `response_type=code` and `code_challenge_method=S256`. After authorization, 303 redirects to the registered client with code and opaque state.
- `POST /identity/v1/token`: Form-encoded `authorization_code` grant, single-use 90-second code, exact client+redirect match, PKCE verifier, registered client and active-account checks. Returns an audience-scoped, 5-minute RS256 access token.
- Both routes are absent (`404`) unless `DRAGONZPYDER_IDENTITY_HTTP_ENABLED=1`. In Railway `production`, additionally requires `DRAGONZPYDER_IDENTITY_ALLOW_PRODUCTION=1`. **Neither variable should be set in production at this stage.**
- This does not expose ID tokens, OIDC metadata, refresh tokens, Google or Discord login. No login/session creation routes are exposed. Existing personal/Operly authentication is unchanged.

## Gaps before any users can authenticate
1. **User sign-in**: protected credential validation for imported password hashes, Google/Discord callbacks, account-link proof, signup/reset/verification, login rate limits, anti-enumeration and recovery. Never turn a Discord channel link into a login credential without proof.
2. **Client UX**: actual interactive identity-origin login and consent screens, authorization request anti-CSRF, and registered clients for Operly Web and DragonZpyder Web. Browser origin checks are not a substitute for client UX.
3. **OIDC**: ID token claims and nonce binding, metadata/discovery, refresh rotation, logout and revocation propagation, account-disable and MFA policies, verified JWKS rotations and signer key isolation from inference/agent processes.
4. **Persistence**: apply staged SQL only to a dedicated, restored database with correct roles. Phase D currently forbids active accounts and Phase E clients are disabled. Run real PostgreSQL tests for concurrent code redemption and session revocation.
5. **Operly**: validate issuer/audience/signature/token type from pinned JWKS, resolve canonical subject and issue a *separate* first-party Operly session while enforcing local Workspace memberships.
6. **Rollout**: restore/backup dry runs, reconciliation of user IDs, verified Google/Discord bindings, old-session compatibility and rollback; enable only after security review and canary success.

Identity routes must never use model-gateway credentials or allow a browser to provide `sub`. Signing key isolation and revocation architecture are not completed by Phase F.
