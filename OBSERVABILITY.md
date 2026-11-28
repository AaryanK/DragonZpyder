# DragonZpyder inference tracing and usage ledger

## Shipped foundation

**Entry point:** `api/main.py` → `api/observability.py` → `api/usage_ledger.py`.

- Server-to-server `/v1/chat/completions` and `/internal/v1/chat/completions`
  use the **same** OpenRouter request path. Existing inference token stays valid.
- Each completion attempt receives an immutable request ID and a trace correlation ID.
  HTTP response headers: `X-DragonZpyder-Request-Id`,
  `X-DragonZpyder-Trace-Id`, `X-DragonZpyder-Audit`.
- OpenTelemetry spans contain request ID, app identity, requested/served model,
  token counts when provider-supplied, status and elapsed time. **Never raw
  prompts, responses, tool arguments, API keys, or cookies.**
- Optional Langfuse OTLP export includes distributed `traceparent` context.
  Operator must configure Langfuse; no credentials are hardcoded.
- Append-only Postgres ledger stores each attempt keyed by request ID,
  including request/response hashes, provider generation ID, attribution,
  token breakdowns, provider-reported cost if available, and failure codes.
- **Exact request/response payloads** can be retained *encrypted* with
  AES-256-GCM after configuring the separate audit encryption key. Payload
  content is **not** captured by default.
- `/internal/admin/usage`: gateway usage totals and per-app/per-model breakdown,
  authenticated with an **independent** admin service credential.
- `/admin`: React usage dashboard served only for an authenticated Operly
  account whose email is in the explicit administrator allowlist. Its data is
  served by FastAPI using the private gateway token; never exposed to the browser.

### Configure DragonZpyder API on Railway

| Variable | Purpose |
| --- | --- |
| `DRAGONZPYDER_USAGE_DATABASE_URL` | Dedicated Postgres URL for immutable usage events. Do **not** use an ephemeral SQLite database. |
| `DRAGONZPYDER_USAGE_REQUIRED=1` | Fail startup when the usage database is missing/unreachable, and withhold a result when its usage record cannot be persisted. Enable only after DB migration and an operational runbook exist. |
| `DRAGONZPYDER_APP_KEYS_JSON` | Optional JSON mapping unique app slug → randomly generated >=32-char bearer credential, e.g. `{"querypedia":"<secret>","operly":"<other-secret>"}`. Legacy `DRAGONZPYDER_RUNTIME_TOKEN` remains valid and recorded as `legacy`; callers must migrate to unique app credentials for reliable attribution. Never trust a browser-supplied app-name header. |
| `DRAGONZPYDER_ADMIN_TOKEN` | Unique >=40-char private token used *only* for reporting; must also be set on DragonZpyder Web. Must not equal inference tokens. |
| `DRAGONZPYDER_LANGFUSE_HOST` | HTTPS base URL of the Langfuse instance (without trailing path). |
| `DRAGONZPYDER_LANGFUSE_PUBLIC_KEY`, `DRAGONZPYDER_LANGFUSE_SECRET_KEY` | Langfuse project API credentials for OTLP exports. |
| `DRAGONZPYDER_AUDIT_ENCRYPTION_KEY` | Optional **32 raw bytes** encoded as URL-safe base64 for encrypted payload capture. Store as a sealed secret. Rotate using an envelope/key-ID strategy before production use. |

### Configure DragonZpyder Web on Railway

- `DRAGONZPYDER_ADMIN_EMAILS`: comma-separated account email allowlist.
  **Empty denies all access** to the admin page.
- `DRAGONZPYDER_ADMIN_TOKEN`: same private reporting credential as API.
- `DRAGONZPYDER_API_ORIGIN`: existing private Railway URL
  (`http://dragonzpyder-api.railway.internal:8080`).

The client never receives admin credentials. A verified Operly login is not,
by itself, enough to access the admin endpoint.

### Data accuracy and compliance

- Missing provider token usage and cost are `NULL`, never silently `0`.
  Report `missing_token_usage` and `missing_cost`.
- Usage estimates must not be treated as invoices or charged to customers.
  Reconcile provider generation IDs and cost against OpenRouter records.
- `DRAGONZPYDER_USAGE_REQUIRED=1` is required before treating the ledger as
  authoritative. In default compatibility mode, requests continue even
  without storage, and the `X-DragonZpyder-Audit: unavailable` header exposes
  the lack of persistence. **This is not yet billing-grade.**
- Encrypted payload storage does not automatically authorise admin access to
  read customer prompts. Payload inspection requires a separate audited
  support-access protocol, explicit retention policy and scoped permissions.
- Trace IDs link services, but unmodified clients, the legacy Operly agent and
  the Web AI Mesh still have uncentralised provider routes. Until those are
  migrated, do **not** claim complete platform-wide tracing.
- Zero-sampling records are restricted to the dedicated Postgres ledger;
  OpenTelemetry OTLP transport can lose spans during outages and is not the
  financial source of truth.

## Next integration milestones

1. Provision the dedicated Postgres instance, set the DB URL and both admin
   credentials, and configure a Langfuse workspace. Verify a real completion
   leaves both one ledger row and a corresponding OTel trace. Then enable
   fail-closed accounting.
2. Querypedia, AI Mesh and Chat Lab now have central, scoped gateway paths.
   Operly remains a separate migration. Add dedicated **tool-calling** APIs
   when LangChain/LangGraph workflows are introduced.
3. Add a secure trace explorer with search by request ID, model, app, user,
   workflow, span, timing and usage. Do not expose raw payloads by default.
4. Instrument LangChain/LangGraph agent steps and future n8n/MCP executions
   using OTel `traceparent` and per-step IDs, including replay boundaries,
   approvals, retries and model usage.
5. Add durable provider cost reconciliation and AIC customer-billing ledgers
   separately from raw inference usage.

## Tests

```sh
python -m pip install -r api/requirements.txt pytest
pytest -q api/tests/test_fastapi_gateway.py api/tests/test_usage_audit.py
python -m pip install -r web/requirements.txt pytest
pytest -q web/tests/test_admin_protection.py
cd web/frontend && npm install && npm run build && npm run test
```


## AI Mesh, Chat Lab and Querypedia central routing (October 2026)

OpenRouter completions and media are now routed through the **DragonZpyder API
service**, never directly from the Chat Lab or AI Mesh web service. AI Mesh
keeps its per-user session/CSRF, catalogue validation, low-cost model filter,
confirmation UI and short-term quotas. The gateway independently verifies
a dedicated app bearer token, checks a fixed operation allowlist, logs model
usage and attaches request/trace IDs to responses.

| Application | Railway service variable | Gateway app ID | Allowed API scope |
| --- | --- | --- | --- |
| AI Mesh | `DRAGONZPYDER_MESH_GATEWAY_TOKEN` | `ai-mesh` | Model catalogues; chat/vision SSE; image/audio/video jobs and polls |
| Chat Lab | `DRAGONZPYDER_CHAT_GATEWAY_TOKEN` | `chat-lab` | Chat completions only (including attachments) |
| Querypedia | `DRAGONZPYDER_QUERYPEDIA_TOKEN` | `querypedia` | Existing filtered `/v1/chat/completions` text endpoint |

The API service has `DRAGONZPYDER_APP_KEYS_JSON` with matching operator-issued
per-app secrets. Use **random distinct secrets** and do not reuse the
`DRAGONZPYDER_RUNTIME_TOKEN`, which is kept for existing Operly/internal
compatibility. Separate `DRAGONZPYDER_MESH_RECEIPT_SECRET` signs expiring
video-job proofs without relying on the provider key.

The server-side gateway endpoint `/internal/provider/<approved path>` is
restricted to first-party app credentials. **Do not expose this endpoint or
these bearer tokens in React/JavaScript.** Operly remains unchanged.

All supported AI Mesh text, vision/PDF, image, audio, video and provider
catalogue calls now transit the gateway. Paid inference records are written
by the central ledger *when a database is configured*. Text streaming
relays SSE while collecting provider final usage data, when supplied.
Binary media are logged via content hash and size; their raw bytes are not
stored as prompt/response JSON.

Operational limitations: OpenRouter may omit token breakdowns, costs or
stream final usage (especially for some media). Unknown values remain null.
Model catalogues and video polling receive OpenTelemetry spans but are not
chargeable model generation records. The encrypted prompt/response escrow
remains optional. Configuring this routing **does not** activate PostgreSQL
or Langfuse by itself: the infrastructure is deployed separately.

Validation: `api/tests/test_provider_gateway.py`, the existing web Mesh and
Chat Lab tests, and Querypedia's `tests/test_querypedia.py` must pass.

## Operations control center (source candidate, November 27, 2026)

The existing /admin page retains inference usage and adds lazy, read-only panels
for Railway deployment inventory (DragonZpyder and Operly), recent Web edge-log
samples, GitHub develop commits/PRs/CI, and Langfuse v2 observation metadata.
New endpoints require an allowlisted native DragonZpyder session; legacy-only
Operly login cannot read these panels. Each response is bounded, no-store,
uses fixed provider endpoints, and sends neither browser cookies nor provider
credentials to the frontend. No mutations or arbitrary provider queries.

Configure **Web service** secrets separately:
- DRAGONZPYDER_ADMIN_RAILWAY_DRAGONZPYDER_TOKEN and DRAGONZPYDER_ADMIN_RAILWAY_OPERLY_TOKEN:
  dedicated environment-scoped Railway project tokens, not a workspace token.
  The implementation performs only fixed GraphQL reads; provider tokens may
  carry broader authority and must remain server-side. Inventory IDs are fixed
  to the current production environments.
- DRAGONZPYDER_ADMIN_GITHUB_TOKEN: optional fine-grained repository read token
  for Contents, Pull requests and Actions; otherwise public API limits apply.
- DRAGONZPYDER_ADMIN_LANGFUSE_HOST, DRAGONZPYDER_ADMIN_LANGFUSE_PUBLIC_KEY,
  DRAGONZPYDER_ADMIN_LANGFUSE_SECRET_KEY: dedicated project credentials for a
  supported HTTPS Langfuse cloud origin; do not paste tokens into code.

Traffic is limited to 200 recent edge requests from the latest Web deployment.
Edge regions are not visitor countries; no raw paths, source IPs, unique users,
referrers or historical totals are inferred. Langfuse reads up to 50 recent
observations, excludes payloads and identifiers of users, and does not claim
complete coverage. No personal conversations, memory contents, secrets, or
workspace records are exposed. Support access to individual customer content
requires a separate durable audit, purpose/permission/retention controls and
authorization review. Future phases: durable aggregated traffic and geolocation,
resource time series, workflow health, trace pagination, identity aggregates,
correlation, and audited support access. CI and live credential-backed
validation are pending; do not claim production deployment or complete analytics.

### Product and harness activity

The native-admin operations tab proxies the existing independent admin service
token to /internal/admin/activity. This endpoint queries only static, aggregate
SELECTs against the existing agent database, with read-only transactions and
8-second source deadlines. It reports request states and UTC daily distinct
request owners, active conversation counts, workflow and Personal goal states,
recent native memory-entry counts and runtime initialization/capability flags.
These are not registered-account totals, historical imported conversations, or
verified execution results. Each missing table/source remains unavailable;
no identity DB role is widened. Existing usage summary adds UTC daily tokens,
provider cost, missing-cost counts, call failures and p95 inference duration.
Langfuse observation search and pagination remain metadata-only and use existing
LANGFUSE_BASE_URL/PUBLIC_KEY/SECRET_KEY on Web if dedicated overrides are absent.
The new operations path requires a stable ID from the verified native profile
and logs a hashed admin actor with the source on successful reads; this is
operational logging, not a durable support-content access audit. No customer
conversation or memory bodies are returned. No provider calls incur inference
cost. Additional tests assert bearer scope and protected Web proxying. CI and
credential-backed tests are required before claiming deployment.
