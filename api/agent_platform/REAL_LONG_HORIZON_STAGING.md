# Long-horizon real-model tool selection: isolated staging

This is an end-to-end **three-wake** infrastructure objective: the same PostgreSQL goal resumes at the next five-minute cron execution, invokes a *metered model* to select an approved local tool, actually executes the tool, persists its receipt, and stops after three distinct successful tools. The model chooses among unfinished options, but it **does not authorize** them. No raw shell, personal data, Operly account access, external write, or provider secret enters any prompt.

## Exactly what it tests

- A fixed internal goal ID: `staging-worker-health-3-wake-v1`
- Three read-only tools: `time.now`, `system.memory`, `system.disk`
- Each wake makes **at most one** model request and at most one real tool call.
- The model must return precisely one OpenAI-style tool call with empty JSON arguments and a name in the remaining allowlist. A malformed model response means no tool is called.
- PostgreSQL holds an authenticated fixed goal, step index, unique (goal, step) records, unique (goal, five-minute bucket) records, tool-result hashes and state. It enforces one read-and-advance transaction at a time.
- A same-interval delivery reports sleeping. A later delivery restores prior history from PostgreSQL and cannot execute a tool already in the receipt ledger.
- A cancelled or completed goal cannot invoke a model.
- The objective ends after exactly three successful steps. `readback` proves persisted state matches the computed tool result; it does **not** prove full host health or externally attest a machine.
- Model failure is sanitized and stops further work after three consecutive failed intervals. The operator must investigate before retrying.

## Verification

CI uses a fake model returning valid/invalid tool calls and a **real disposable PostgreSQL** database. It tests concurrent duplicate invocations, distinct tool selection, cancellation, and forced reopens of database connections after each wake. This is not the same thing as a real paid model response.

A live staging run needs a dedicated Railway cron service, source `AaryanK/DragonZpyder` branch `test/real-scheduled-long-horizon-staging-20261119`, root `/api`, Dockerfile `/api/Dockerfile.staging`, command:

    python -m agent_platform.persistent_tool_canary

With cron:

    */5 * * * *

And server-only env configuration:

    DRAGONZPYDER_STAGE=staging
    DRAGONZPYDER_LONG_HORIZON_CANARY_ENABLED=1
    DRAGONZPYDER_LONG_HORIZON_SCHEMA_INSTALL_ALLOWED=1
    DRAGONZPYDER_AGENT_USE_GATEWAY=1
    DRAGONZPYDER_AGENT_PRODUCTION_MODE=1
    DRAGONZPYDER_LONG_HORIZON_DATABASE_URL=<PRIVATE-STAGING-POSTGRES-DSN>
    DRAGONZPYDER_AGENT_GATEWAY_BASE_URL=<AUTHORIZED-STAGING-GATEWAY-ENDPOINT>
    DRAGONZPYDER_AGENT_GATEWAY_TOKEN=<SERVER-ONLY-SECRET>
    DRAGONZPYDER_AGENT_MODEL_ID=<ALLOWED-METERED-MODEL>
    DRAGONZPYDER_RUNTIME_ALLOWED_MODELS=<EXPLICIT-ALLOWED-MODEL-SET>

Do not set a direct OpenRouter key. The gateway must already enforce per-request cost/rate limits. Never supply a customer or production database. The schema flag exists only for this dedicated staging database; remove it after initial provisioning.

**Expected evidence:** three distinct scheduled launches separated by five-minute buckets; three model selections (actual provider response, not fake); real tool receipts with distinct tool IDs, PostgreSQL step indices 1, 2, 3; further wakes report completed, do not spend. Validate logs and DB. Do not claim success before seeing this evidence.

## Real Operly reads: separate authorization boundary

The three-wake demonstration **does not** complete an Operly business read. The accessible Operly deployment is production-only. Operly PR #373's private read-only broker is unmerged and not installed in a disposable Operly staging environment; the existing isolated five-minute business canary tests only a mocked broker transport. Before the live Operly test:

1. Create an isolated Operly staging instance with dedicated blank Postgres and a synthetic test workspace, user and records.
2. Deploy the read-only broker with its required auth, generate a genuine limited user delegation, and verify the user has only workspace read access.
3. On every five-minute Hatchet wake, ask the trusted Operly issuer for a **new** read-only lease after membership, user consent and role revalidation, never persist the lease or user data in the goal ledger or model context.
4. Execute `workspace.summary.read`, `workspace.attention.list`, `workspace.activity.list` through the real Kernel and compare to independently queried staging data.
5. Revoke the test workspace access and confirm subsequent wake fails closed. No invoice, payment, sale or membership mutation is authorized.

This is deliberately a **two-phase proof**: infrastructure persistence and model tool selection first, real business authorization second. Do not merge all stacked branches on the strength of synthetic tests or a few successful cron starts.
