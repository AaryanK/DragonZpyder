# DragonZpyder / Operly credential and authority cutover
**Railway production variable-name audit — 2026-11-23.**
All findings are *variable names* only. OAuth-connected Railway returns **no
secret values**. Never paste API keys, database passwords, JWT private keys,
OAuth refresh tokens or password hashes into GitHub, chat, logs or a model.

## Ownership and relocation matrix

| Credential family | Existing source | Destination | Action |
|---|---|---|---|
| `OPENROUTER_API_KEY` | DragonZpyder API **already has it**; Operly also has a legacy copy | DragonZpyder API | **No copy needed.** Retire Operly key only after no Operly runtime/canary uses it. |
| Agent gateway, `DRAGONZPYDER_AGENT_GATEWAY_TOKEN`, `DRAGONZPYDER_OPERLY_PERSONAL_AGENT_TOKEN`, `DRAGONZPYDER_OPERLY_MCP_SERVICE_SECRET` | DragonZpyder API already configured; Operly has corresponding service variables | Server-only paired services | **Keep / verify** length, expiry and signed delegation. Never expose to a browser or MCP response. |
| Hatchet `HATCHET_CLIENT_TOKEN` | DragonZpyder Agent API/Worker | DragonZpyder | Already present. Keep Operly workflow events/Workspace data in Operly until externally dispatched and verified. |
| Langfuse `DRAGONZPYDER_LANGFUSE_*`, model research credentials, `SARVAM` | DragonZpyder API | DragonZpyder | Already present. Do not blindly copy duplicates. |
| `GOOGLE_AUTH_CLIENT_ID` | Operly Web/API | `DRAGONZPYDER_IDENTITY_GOOGLE_CLIENT_ID` on DragonZpyder API | Browser OAuth *public client ID* can be reused **only if the Google project allows the DragonZpyder Web origins**. Verify the exact Google app and registered JavaScript origins first. The connected Railway OAuth tool does not reveal values. |
| `DISCORD_AUTH_CLIENT_ID`, `DISCORD_AUTH_CLIENT_SECRET` | Operly | DragonZpyder identity provider equivalents | Use newly scoped Discord application credentials or securely transfer only after verifying the new callback `https://api.dragonzpyder.xyz/identity/v1/provider/discord/callback`; the backend secret is never browser-visible. The cross-host browser session handoff is **not yet complete**, so keep Discord native sign-in OFF. |
| `GOOGLE_OAUTH_CLIENT_SECRET` | Operly connectors | **Operly** | Do not confuse business Google Drive OAuth with first-party Google sign-in. Business OAuth remains in Operly. |
| `CANVA_CLIENT_SECRET`, Zoho refresh token, Gmail/mail delivery, Workspace connector secrets, `MCP_OAUTH_SECRET` | Operly | **Operly** | Retain. Operly owns business integrations, its MCP authorization, Workspace permissions and audit. |
| `DISCORD_BOT_TOKEN` | Operly | Operly's channel gateway | Retain until signed channel-specific DragonZpyder delegation is verified. It does not belong in model context. |
| `GEMINI_API_KEY`, `GROQ_API_KEY`, `NVIDIA_API_KEY`, `OLLAMA_API_KEY` and legacy lowercase variants | Operly / Worker | DragonZpyder model-gateway only **if actually required** | Audit live model calls first. Do not proliferate dormant keys. Rotate/revoke old provider keys after successful live parity. |
| `AUTH_TOKEN_PEPPER`, `SESSION_SECRET`, `OPERLY_APP_IDENTITY_SECRET` | Operly | **Do not transfer** | These authenticate legacy sessions; native DragonZpyder must use its own issuer keys, session hashes, and account activation. |
| `DRAGONZPYDER_IDENTITY_SIGNING_KEY_PEM`, `DRAGONZPYDER_IDENTITY_SIGNING_KID`, `DRAGONZPYDER_IDENTITY_GRANT_HASH_KEY` | **Missing** from DragonZpyder API | DragonZpyder API | **Create new independent secrets** (RSA private key + identifier + grant HMAC key), install via Railway secure variables. Never reuse Operly's cookie/MCP signing key. |
| `DRAGONZPYDER_MCP_FERNET_KEYS` | **Missing** | DragonZpyder API | Generate a new independent Fernet keyring, store server-side and back up to an authorized vault. Do not use Workspace connector tokens as the Fernet key. |
| `DRAGONZPYDER_MCP_DATABASE_URL`, egress network policy | Not provisioned | DragonZpyder API | Separate encrypted OAuth store and actually enforced outbound egress controls required before enabling external user MCP. |

## Work completed by audit

- New dedicated private identity database service: **Postgres-oiNi** in
  Railway project **DRAGONZPYDER**. Credentials are Railway-generated; none
  were exported.
- DragonZpyder API `DRAGONZPYDER_IDENTITY_DATABASE_URL` references that
  service internally; native feature flags remain OFF.
- Transactional schema bootstrap merged as DragonZpyder PR #130, with real
  disposable PostgreSQL acceptance. A one-shot installer service is **staged**,
  not deployed, awaiting explicit operator release.
- Operly `OPERLY_MCP_CLIENTS_JSON` now registers **dragonzpyder** as a
  public PKCE client with exact callback:
  `https://dragonzpyder.xyz/dz/internal/mcp/oauth/callback`.
  This creates NO Workspace ClientGrant.
- DragonZpyder `DRAGONZPYDER_MCP_OAUTH_CALLBACK_URL` matches the callback,
  but external MCP service activation, approved capability manifest and
  end-user authorization are still disabled.

## Native identity setup order

1. Install the **single-transaction** empty-database schema with an operator
   migration role. Read back every table/constraint and verify no users
   activated and both OIDC clients remain disabled.
2. Provision a restricted, **non-superuser** API role and replace any
   administrative `DRAGONZPYDER_IDENTITY_DATABASE_URL` reference with its
   scoped credentials. The initial bootstrap reference uses template database
   credentials strictly while native HTTP flags remain OFF.
3. Install independent issuer signing/HMAC keys through Railway secrets.
   Configure `DRAGONZPYDER_IDENTITY_ISSUER=https://api.dragonzpyder.xyz`,
   public Google client ID, exact Google JavaScript origins
   `https://dragonzpyder.xyz` and `https://www.dragonzpyder.xyz`, and
   browser callback/cookie behavior.
4. Prepare a **private, operator-reviewed** Operly source snapshot of
   `app_users`, `auth_identities` and verified `external_identities`,
   with a backup checksum, frozen row counts, and per-provider subject
   uniqueness. Do not expose emails/password hashes to the agent.
   Run `api/identity/reconciliation.py` and `importer.py` in an isolated
   migration process. Quarantine ambiguous or unverified bindings.
5. Existing `source_operly_user_id` and canonical DragonZpyder subject
   remain uniquely mapped; **never merge by email**. Activate imported
   identities individually only after verified password/provider proof and
   operator migration approval. Continue honoring existing Operly sessions
   until migration parity and rollback are demonstrated.
6. Test actual new/old account login, password recovery, logout/revocation,
   provider linking, account deletion and cross-account permissions. Activate
   native Web and Android only after checking session, chat/history, files,
   approvals, voice, Mesh and reconnects on real devices.

## Optional Operly MCP registration

- Operly still requires a **user/workspace/client-specific active grant**.
  Operator registration alone must never expose Workspace tools.
- Retrieve an authorized real `tools/list` from Operly MCP, audit
  read-only versus mutating tool IDs, then populate
  `DRAGONZPYDER_MCP_OAUTH_PROVIDERS_JSON` with exact reviewed names.
  Do not invent `tasks.list` or other capabilities from examples.
- Install `DRAGONZPYDER_MCP_FERNET_KEYS`, a dedicated MCP database, and an
  enforced network egress policy. Only then consider enabling
  `DRAGONZPYDER_MCP_USER_CONNECTIONS_ENABLED`,
  `DRAGONZPYDER_MCP_EGRESS_FIREWALL_ENFORCED`,
  `DRAGONZPYDER_MCP_USER_CONNECTIONS_PRODUCTION_APPROVED` and
  `DRAGONZPYDER_OPERLY_USER_OAUTH_ENABLED`.
- A connection must be revoked at both stores; scheduled Hatchet calls
  revalidate individual user and Workspace authority, not service tokens.

## No-go retirement conditions

**DO NOT delete Operly's old model keys or intelligence services** until:
(a) all mounted chat endpoints are delegated and live-verified;
(b) an actual two-account A/B test passes; (c) attachments/approvals,
Discord and scheduled work have valid replacement routes; (d) in-flight work
is drained, (e) rollback has been rehearsed, and (f) Operly retains Workspace
data, Kernel, MCP gateway and permission enforcement. Passing mock CI alone
is not a live cutover receipt.
