# Universal MCP Connection Manager (review-gated)

This is an additive connection layer for api/agent_platform/mcp_broker.py.
The broker continues using langchain-mcp-adapters (the upstream SDK); OAuth
exchanges use Authlib. There is no second MCP protocol stack or agent runtime.

## Boundaries and status

- Operly Personal MCP and Operly's business authorization, memberships, leases,
  consent and approvals are unchanged. The new registry reserves "operly"; it
  cannot impersonate the Operly broker or replace its authority.
- Signed Personal runs may carry up to ten *opaque account IDs*, never tokens.
  Those IDs are resolved inside the backend from the user-scoped PostgreSQL
  store, with token refresh and permission checking before each tool call.
- Every third-party tool requires an operator-reviewed READ-ONLY exact name.
  Scheduled executions additionally require a scheduled_tools entry. There is
  no generic unattended mutation path. Human approval is not inferred from
  OAuth scopes or MCP tool annotations.
- Chat/state cannot introduce MCP URLs. The optional public reviewed catalog
  and private-account catalog are mutually exclusive until one catalog
  coordinator is deployed.
- A returned receipt proves an SDK call, not independently verified effects.
- Browser OAuth uses the existing first-party identity session and CSRF check.
  Client ID, scopes, PKCE challenge and state may appear in the authorization
  URL, never access/refresh tokens. The callback consumes server-side state.
- This code is **not production-approved**. No unrestricted third-party MCP
  endpoints, remote commands or writes are enabled.

## Configuration and rollout

Apply the migration api/agent_platform/migrations/20261122_mcp_connections.sql
MANUALLY using a database migration role. Do not grant this role identity-DB
permissions or access to LangGraph checkpoints. Use a separate, backed-up
PostgreSQL database and least-privilege runtime role. Configure:

- DRAGONZPYDER_MCP_DATABASE_URL: dedicated PostgreSQL URL accessible only to
  the API (not the browser, agent, sandbox or Hatchet).
- DRAGONZPYDER_MCP_FERNET_KEYS: comma-delimited URL-safe Fernet keys, newest
  first; generate a random key with cryptography. Store in a secrets vault,
  not git. Rotating keys requires retaining old keys until ciphertext is
  re-encrypted; deleting all keys permanently loses connection authority.
- DRAGONZPYDER_MCP_OAUTH_CALLBACK_URL: exact HTTPS callback ending in
  /internal/mcp/oauth/callback, on the same host as DragonZpyder's HttpOnly
  __Host-dz_identity browser session. Pre-register this URI with each AS.
- DRAGONZPYDER_IDENTITY_DATABASE_URL / DRAGONZPYDER_IDENTITY_ISSUER: existing
  identity database and exact origin, with live session and CSRF verification.
  Secure/HttpOnly/SameSite=Lax browser session is required.
- DRAGONZPYDER_MCP_OAUTH_PROVIDERS_JSON: static operator-reviewed manifest,
  at most 100 entries, bounded size. Never sourced from user/LLM content.
- DRAGONZPYDER_MCP_EGRESS_FIREWALL_ENFORCED=1: operator attestation ONLY.
  Before setting, deploy and independently test an actual outbound firewall
  / egress proxy: enforce DNS resolution to public IPs, block all private,
  link-local, metadata and loopback destinations, prevent DNS rebinding, deny
  cross-host redirects and allowlist both reviewed MCP and issuer hosts.
  Application HTTPS URL checks alone are NOT sufficient against SSRF.
- DRAGONZPYDER_MCP_USER_CONNECTIONS_ENABLED=1: activate only in isolated
  staging after verifying the above. No automatic schema installation.
- DRAGONZPYDER_MCP_USER_CONNECTIONS_PRODUCTION_APPROVED=1: separate production
  override, deliberately NOT configured or recommended until independent
  security review, penetration tests and live provider conformance testing.

The application refuses production activation without both the primary gate
and the explicit production approval variable. Keep all three flags OFF in
production. Use an actual operator-level egress firewall; a claimed flag is
not proof of one.

Example fictional manifest (replace with *verified* provider endpoints):

    [
      {
        "provider_id": "archive",
        "description": "Reviewed read-only archive lookup",
        "mcp_url": "https://archive.example.com/mcp",
        "issuer": "https://login.example.com",
        "registration": "pre_registered",
        "client_id": "registered-public-client",
        "readonly_tools": ["documents.lookup"],
        "scheduled_tools": ["documents.lookup"],
        "requested_scopes": ["documents.read"]
      }
    ]

Registration modes: pre_registered (client_id, optional client_secret_env),
client_id_metadata (client_id_metadata_url, HTTPS URL also used as client_id),
dynamic (RFC 7591 registration_endpoint discovered from the PINNED issuer).
If provider metadata does not confirm PKCE S256, fail closed. HTTP transports
are streamable HTTP only. PKCE, issuer, resource binding, CSRF state and token
refresh are independent of DragonZpyder permission checks.

Do not use example.com as a real endpoint. Never put client_secret directly
in the manifest; use its environment variable name. A public Client ID Metadata
Document must already be published and reviewed before use.

## Browser connection flow

All routes require a current first-party identity browser session; mutating
routes require the existing x-dz-csrf header and exact Origin:

- GET /internal/mcp/providers: reviewed provider names and requested scopes.
- POST /internal/mcp/connections/{provider_id}/start with {"label": "Work"}:
  returns a provider authorization URL; navigate the browser there.
- GET /internal/mcp/oauth/callback: provider redirect; one-time state, issuer,
  session binding, PKCE exchange. Returns HTML only; no token or auth code.
- GET /internal/mcp/connections: opaque IDs, labels, scope and status only.
- DELETE /internal/mcp/connections/{connection_id}: immediate local revoke,
  credential deletion, best-effort provider RFC 7009 revocation. A provider may
  keep the token live until expiry if it lacks revocation support or is down.

Account labels are user descriptions, NOT verified provider account identities.
Multiple accounts under one provider get distinct opaque connection IDs; the
manager never silently falls back to another account.

## Chat, Hatchet and authorization

The signed Operly Personal request adds optional mcp_connection_ids. The
backend must verify the Operly subject is identical to the first-party
identity subject used to create the connection. If identity mapping is not
already guaranteed, DO NOT pass aliases: explicitly implement a trusted
identity mapping before enabling them in Operly's frontend.

A selected account is NOT a permission to invoke arbitrary third-party tools.
The operator-reviewed tool allowlist, live user ownership, OAuth scopes at the
provider, DragonZpyder signed session/user scope and any required human
approval are independently enforced. The generic catalog exposes only
reviewed reads; no mutations requiring approval are included.

On a Hatchet wake, the existing Operly re-delegation is required. A third-party
account selection is stored as a nonsecret sha256 in dz_mcp_goal_selections and
must be identical on all subsequent wakes. The API rechecks ownership,
revocation, manifest policy, and token freshness before each discovery and
invocation. Scheduled selected capabilities require scheduled_tools. An unknown
effect is never automatically retried. Hatchet contains only IDs, not tokens,
refresh credentials, client secrets or auth codes.

The current goal_schedule tool creates Operly-only goals. To authorize
third-party scheduled connections, a trusted scheduler must explicitly
associate the already user-approved opaque connection selection at goal
creation; do not let an LLM choose or rewrite a selection. Migrate goal
selections before enabling feature flag for scheduled workers.

## Acceptance evidence and limitations

The accompanying offline test suite covers encrypted principal binding,
PKCE S256, one-time state and session CSRF, issuer mix-up rejection, malicious
endpoint rejection, explicit multi-account selection, cross-user denial,
single-flight refresh, revocation, scheduled policy and two-provider SDK tool
alias isolation. It uses synthetic OAuth and SDK tools; it does NOT establish
successful live OAuth exchanges, provider revocation, browser UX, firewalled
DNS egress or a production end-to-end scheduled job.

Required before promotion: a staging deployment with real firewall, a reviewed
OAuth provider in each registration mode, explicit user-account identity
mapping, actual callback and refresh/revocation traces (redacted), a live
simultaneous two-provider read test, an actual Hatchet wake after token expiry
and revocation, an approval-policy security review, and security-owned signoff.
Report exact evidence and tests; a green mocked CI cannot certify production.

Keep delete/expiration cleanup for dz_mcp_oauth_attempts on the DB maintenance
schedule, and define encryption key rotation/recovery and backup retention.
