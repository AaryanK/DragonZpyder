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
2. Assign individual app credentials and migrate Querypedia, AI Mesh and
   Operly inference one by one. AI Mesh currently talks to OpenRouter directly;
   the central gateway needs separate scoped **streaming, image, audio and
   tool-calling** endpoints before changing these clients. Do not break them
   by forcing requests through the existing text-only endpoint.
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
