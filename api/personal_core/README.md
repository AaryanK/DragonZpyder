# DragonZpyder Personal Core — disabled-by-default staging foundation

DragonZpyder is the individual AI computing substrate. Operly retains workspace
permissions, organizations, business data and approval workflows. No business
permissions are moved or inherited by the personal API.

## Implemented now
- Feature-flagged personal chat API (`POST /v1/chat`) with bounded user-provided
  conversation history; no persistent chat logs or external actions.
- Cryptographically verified, scoped OIDC **access** tokens for central identity;
  no browser cookies, caller-provided user IDs or legacy API tokens.
- Operator-reviewed model allowlist, live OpenRouter prices, conservative
  request reservation, cheapest approved text model under a price ceiling.
- Metered internal gateway route requiring a separate personal service token;
  upstream requests are constrained by OpenRouter provider `max_price`,
  price-priority routing and a data-collection exclusion.
- Atomic PostgreSQL per-user daily reservations with unknown-cost charges
  reserved rather than assumed free. No user identifiers stored in cleartext.
- `GET /v1/me/budget`; separate defaults of $0.03/user/day, 25 calls/day.
  These are initial safety values, not a permanent product/plan restriction.

## NOT implemented yet
- OIDC issuer provisioning and OAuth PKCE login UX. Until then, public
  registration and personal chat must remain disabled.
- Browser/computer runtime for personal principals, MCP permissions, persistent
  personal memory and full history erasure, files, multimodal, agent delegation,
  video/audio/voice, scheduled personal tasks, BYOK, free/local inference.
- Per-provider verified usage reconciliation, cancellation/recovery, privacy
  review and account-deletion controls.
- A public API or deployment with unbounded spending.

## Deployment contract
An optional separate service uses `api/Dockerfile.personal` and
`DRAGONZPYDER_PERSONAL_ENABLED=0` until OIDC and budgets are tested.

Enable only after configuring a backed-up database via
`DRAGONZPYDER_PERSONAL_DATABASE_URL`, a random 40+ character
`DRAGONZPYDER_PERSONAL_ID_HASH_KEY`, trusted HTTPS
`DRAGONZPYDER_PERSONAL_OIDC_ISSUER`,
`DRAGONZPYDER_PERSONAL_OIDC_JWKS`, and
`DRAGONZPYDER_PERSONAL_OIDC_AUDIENCE`.
The identity provider must issue access tokens scoped to
`dragonzpyder:personal`.

`DRAGONZPYDER_PERSONAL_ALLOWED_MODELS` must name explicitly reviewed
text models, and those same models must be enabled on the gateway
`DRAGONZPYDER_RUNTIME_ALLOWED_MODELS` allowlist.

The separate internal metered gateway route uses
`DRAGONZPYDER_PERSONAL_GATEWAY_URL=http://dragonzpyder-gateway.railway.internal:8080/internal/personal/v1/chat/completions`
and service credential `DRAGONZPYDER_PERSONAL_GATEWAY_TOKEN`, equal to
the gateway's `DRAGONZPYDER_PERSONAL_BACKEND_TOKEN` via a secure Railway
variable reference. Gateway must have `DRAGONZPYDER_PERSONAL_GATEWAY_ENABLED=1`,
a persistent usage ledger and a spend-limited OpenRouter key.

The catalog and spending ceilings are intentionally conservative.
No duplicate scheduler, model gateway, user memory backend or Operly agent loop
is introduced here.
