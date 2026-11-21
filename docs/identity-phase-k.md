# Phase K — Browser authorization and consent (still gated)

The identity service remains a module inside the **existing DragonZpyder API**.

### Added
- A registered-client-validated `GET /identity/v1/authorize` endpoint, with an issuer-hosted password sign-in and explicit consent UI (a deliberately minimal, same-origin HTML+JavaScript implementation).
- Consent is a CSRF-protected `POST /identity/v1/authorize`, which creates a single-use code and returns an **exact-registered callback URL** for same-origin JavaScript, or a traditional 303 for non-JS clients.
- OIDC discovery `/.well-known/openid-configuration`, only advertised with both browser authorization and JWKS enabled. Metadata only describes actual code, PKCE, client-audienced ID-token, and refresh capabilities.
- CSP, no-referrer/no-store response policies, HTML escaping, duplicate query key rejection, nonce validation, registered redirect validation and disabled-by-default HTTP flags.
- Synthetic browser/consent/discovery tests are picked up by dedicated identity CI. No production environment flags or DBs were touched.

### Not a production SSO cutover
- Account activation remains explicitly **blocked by Phase D schema**, so no production user can sign in.
- Google/Discord API proof paths already exist but are **not yet integrated into this login screen**.
- Consent is explicit but basic; a complete privacy/scope UX and tested return/error semantics need a final review.
- Key rotation, trusted private-key isolation, dynamic client registry administration, refresh family absolute expiry, robust account recovery, anti-abuse and browser security audit are outstanding.
- Operly must pass its federated callback+session test and be registered as an approved client. Existing Operly sessions stay untouched until a canary is approved.
- Both repos' stacked draft PRs need review/rebase and a restored-database migration rehearsal before live activation.

Dependencies: DragonZpyder #73 → #76 → #78 → #79 → #80 → #81 → #82 → #84 → #86 → #88 → this phase.
