# DragonZpyder-first agent ingress (migration in progress)

## Target ownership

All **AI agent** requests from Web, browser-backed Android, and Operly
integrations must be executed by the DragonZpyder API/harness. This does
**not** mean proxying Operly's business API through DragonZpyder: Operly
remains the authority for workspaces, orders, business permissions and
human approvals. Its MCP integration is optional per connected account.

## Added in this change

- `POST /v2/personal/chat` on DragonZpyder API accepts only a valid
  DragonZpyder first-party browser session plus the paired CSRF token.
  `user_id` / service credentials are not accepted from the browser.
- New conversations have a random UUID, a stored owner and a LangGraph
  checkpoint keyed by verified owner+conversation. Existing IDs require
  owner readback; one conversation's model invocation is serialized across
  API replicas. The API never reissues Operly authentication.
- `GET /v2/personal/session`, `/conversations`,
  `/conversations/{uuid}/messages` let first-party clients restore state.
- Reviewed connected MCP accounts are **optional**. Explicitly selected
  aliases are resolved against the DragonZpyder user's connection manager
  and permissions rechecked before invoking tools. No provider tokens,
  workspace grants, or credentials appear in prompts.
- DragonZpyder Web has a restricted `/dz/*` reverse proxy to the
  DragonZpyder API. It only exposes first-party Personal, password
  login/logout and browser MCP management, not privileged `/internal/*`
  model routes.
- `web/app.js` has a cutover-controlled native Personal path. A Web
  deployment with the gate enabled uses only DragonZpyder Personal
  session/login/chat/history/logout. An unavailable native API is **not**
  silently replaced by Operly. Android PR #110 is a TWA/Custom Tabs
  launcher of this same Web app; it therefore follows that route.

## Flags (ALL disabled by default)

1. Provision, populate and security-review DragonZpyder identity
   accounts and browser sessions. Implement self-service registration
   and provider account linking for general availability.
2. Apply `api/agent_platform/migrations/20261122_first_party_chat.sql`
   to the Agent checkpoint database using an authorized migration role.
3. Verify `DRAGONZPYDER_AGENTS_ENABLED=1` and the metered model gateway,
   checkpoint store, permissions and provider budget are working.
4. Configure `DRAGONZPYDER_IDENTITY_HTTP_ENABLED=1` and
   `DRAGONZPYDER_IDENTITY_ALLOW_PRODUCTION=1` **only after** the
   production identity review and migrations; set the correct
   `DRAGONZPYDER_IDENTITY_ISSUER` to the API origin.
5. Enable `DRAGONZPYDER_FIRST_PARTY_CHAT_ENABLED=1` on API for
   isolated native-client testing. Leave Web cutover OFF.
6. After account migration and device-level acceptance tests,
   enable `DRAGONZPYDER_FIRST_PARTY_WEB_CUTOVER_ENABLED=1` on Web.
   The new Web deployment will no longer call Operly for Agent messages.

**Do not turn on the Web cutover flag yet.** The native identity system
currently provides password login for imported accounts, not public signup.
Operly conversation/artifact migrations, attachment transport, Personal
approvals and memory parity, first-party Mesh/voice authorization, plus the
reviewed Operly-as-optional-OAuth-MCP connection are not yet complete.
The generic MCP manager deliberately excludes an unreviewed `operly`
provider; that is not bypassed by this patch.

## Required release gates

- Test existing account, genuinely new account and disconnected user;
  verify first-party signup, password/OIDC, logout, refresh/revocation
  and no access to either other's conversations or MCP accounts.
- Simulate conflicting chat submissions on multiple replicas and read
  back the durable checkpoint; test database unavailability.
- Confirm provider authorization, per-account tool discovery, expiration,
  live revocation and human approval for mutations, including Hatchet wakes.
- Compare legacy message history, attachments, memory, tool receipts,
  approvals, real Operly business effects and rollback. Retain distinct
  workspace authorization in Operly.
- Confirm web, Android TWA and native callers all reach the first-party API.
  Check that Voice and Mesh never authenticate through Operly after cutover.
- Run CI and live smoke tests with provider charges and spend guards before
  any production flip.

## Rollback

Keep `DRAGONZPYDER_FIRST_PARTY_WEB_CUTOVER_ENABLED=0` until the
production migration is accepted. This PR is additive; legacy
`/api/*` remains for transitional auth, attachments, business flows and
explicit rollback. The old Operly-based route should only be retired after
migration receipts and account deletion/permission revocation parity.
