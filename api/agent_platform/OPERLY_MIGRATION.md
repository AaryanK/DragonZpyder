# DragonZpyder-owned agent harness: first migration slice

Owner: **DragonZpyder**. This branch is **not deployed**.

## The boundary

- DragonZpyder owns Deep Agents, LangGraph checkpoints, model calls and agent turn processing.
- Operly remains the authority for Business/Workspace membership, capabilities, approvals, audit and sandbox/tool execution.
- Existing Operly **Personal** OAuth, conversations and workflows are temporarily brokered until DragonZpyder has its own account identity, connector migration and retention/erasure controls. Do **not** delete those tables or credentials in phase 1.
- Operly calls `POST /internal/agents/operly/run` on the DragonZpyder API. This endpoint requires a **dedicated service secret**, independent of model API credentials.
- A short-lived, Operly-signed capability lease accompanies each run. The lease remains opaque to DragonZpyder and the LLM. On every discovery and call, Operly rechecks current membership, availability, capability scope and risk.
- In this first cut the broker permits **read-only** capabilities only. No external writes, bookings, sends, payments, purchases, shell execution or approval resumes.
- A final assistant message is **not independently verified objective completion**. The result sets `objective_verified=false`.

## Deployment blockers and flags (default OFF)

DragonZpyder API:
- `DRAGONZPYDER_AGENTS_ENABLED=1`
- `DRAGONZPYDER_AGENT_HARNESS_V2=1`
- `DRAGONZPYDER_AGENT_USE_GATEWAY=1`
- `DRAGONZPYDER_AGENT_PRODUCTION_MODE=1`
- `DRAGONZPYDER_AGENT_OPERLY_READONLY_ENABLED=1`
- `DRAGONZPYDER_OPERLY_AGENT_TOKEN` — unique inbound service secret (40+ characters).
- `DRAGONZPYDER_OPERLY_BROKER_URL` — an approved Operly internal URL ending in `/api/internal/agent-tools`, or exact HTTPS Operly host.
- `DRAGONZPYDER_OPERLY_BROKER_TOKEN` — separate broker service secret (40+ characters).
- The already-required model allowlist, gateway authentication, PostgreSQL checkpoint and provider spending controls.

Operly:
- `OPERLY_AGENT_HARNESS_OWNER=dragonzpyder` (default is `operly`).
- `OPERLY_DRAGONZPYDER_AGENT_URL` — approved DragonZpyder API URL ending in `/internal/agents/operly/run`.
- `OPERLY_DRAGONZPYDER_AGENT_TOKEN` — matches DragonZpyder's **inbound** service token.
- `OPERLY_DRAGONZPYDER_AGENT_BROKER_ENABLED=1` — explicitly enable private broker endpoints.
- `OPERLY_DRAGONZPYDER_BROKER_TOKEN` — matches DragonZpyder's **outbound** broker secret.
- `OPERLY_DRAGONZPYDER_DELEGATION_KEY` — independent HMAC signing key retained **only by Operly**.

Configure in a staging environment first, using secret references and restricted network access. **Do not enable on production** until per-user budgets, real-provider smoke, authorization changes during a run, tool-response tainting, privacy handling, rollback, and actual complete-task verification pass.

## Deliberately not covered by this first slice

- Full dynamically installed outbound MCP connections.
- Mutating tools, authorization/approval resume, non-replayable side effects.
- Durable, user-facing goals/jobs, worker recovery and scheduling unified across services.
- Automatic import or migration of Operly Personal conversations, files, memory or connected account credentials.
- Unified multi-tenant accounting for every model/subagent/provider.
- Full LangGraph/Operly workflow replacement; business workflow engine remains in Operly.

**Migration order:** remote harness read-only proof → sandbox/authorized tool relay → durable goal ownership in DragonZpyder → Personal data/connectors migration with identity mapping → retire Operly's model planner/custom harness when matched tests pass. Never delete a permission/audit/migration layer merely because the agent logic moved.


## Universal harness migration slice (November 9)

The following reusable code is now **authored and owned in DragonZpyder**:

| Component | Canonical DragonZpyder source | Status |
| --- | --- | --- |
| LangChain/Deep Agents supervisor | `agent_platform/harness.py`, `runtime.py` | Existing, still staged |
| Scoped tool hub | `agent_platform/capability_hub.py` | Integrated for Operly read tools |
| Operly as a capability source | `agent_platform/operly_broker.py` | Signed lease / read-only |
| Remote MCP SDK adapter | `agent_platform/mcp_adapter.py` | Operator-reviewed, disabled unless firewall and source allowlist are explicit |
| Workflow specification + cron/timezone | `agent_platform/workflows/spec.py` | Ported from Operly, tested for identical semantics |
| Workflow LangGraph executor | `agent_platform/workflows/graph.py` | Bounded read-only execution, wait boundary, no external writes |
| Workflow control-plane preview | `agent_platform/workflows/router.py` | Service-authenticated, no scheduling side effect |
| Hatchet worker and scheduling primitives | `agent_platform/jobs.py`, `worker.py` | Previously in DragonZpyder, operator-only |
| PostgreSQL checkpointer | `agent_platform/runtime.py` | Previously in DragonZpyder |
| OpenRouter, Langfuse, Mem0 | Agent modules + separate API | Previously in DragonZpyder; Mem0 user rollout not certified |

Operly's `packages/workflow/dragonzpyder_client.py` and feature-flagged
`WorkflowProvider._schedule_preview` are compatibility **wrappers**. When
`OPERLY_WORKFLOW_HARNESS_OWNER=dragonzpyder`, Operly sends its authorized
request to DragonZpyder's `/internal/workflows/preview`, which runs the
canonical schedule logic. The old path remains when this flag is unset.

**Not migrated:** runnable recurring cron jobs, shared human approval/resume,
personal OAuth and records, current business workflow definitions, tool provider
credentials, exact-once external effects, billing and durable parent goal
state. Do not delete Operly SQLAlchemy models, workflow migrations or
permission gates while active stored workflows depend on them. A preview
without `job_registered=true` is a preview, not a scheduled task.

**Next required migration:** move workflow definition and run persistence to
DragonZpyder-owned PostgreSQL, attach Hatchet wakeups and event triggers,
and request a NEW scoped Operly capability lease on every waking run rather
than storing the four-minute lease. Only after data parity and live
acceptance may Operly's legacy scheduler be retired. Do not enable the
experimental MCP connector for personal OAuth without proper delegated user
authorization and network egress enforcement.


## Wrapper contexts, owned goals and personal/device migration (November 9)

**Single intelligence provider:** DragonZpyder's LangGraph/Deep Agents
runtime, Hatchet worker, context/capability hub, model gateway and goals store
are the shared execution layer. Operly and NaySchool are separate client
applications with their OWN verified identity and domain capability providers.

**Operly business entry:** The existing signed-readonly capability broker now
returns live, membership-rechecked `workspace_context` on its `/search`
response. DragonZpyder fetches that context prior to running a Workspace
goal, bounds the data to name/timezone/role/mode and labels it explicitly as
untrusted model data. It NEVER uses a workspace name or model-inferred role
as authorization. On every subsequent tool call Operly rechecks actual
workspace identity, capabilities and permissions. Personal requests have
NO workspace context.

**Goal ownership:** `agent_platform/goal_store.py` and
`agent_platform/goal_router.py` provide DragonZpyder-owned encrypted
PostgreSQL goal records, idempotent registration, scoped lookup/cancel and
validated schedule metadata. The runtime refuses to start if the required
migration is missing or `DRAGONZPYDER_GOALS_ENCRYPTION_KEY` is invalid.
Schema: `agent_platform/migrations/20261109_encrypted_goals.sql`.
Feature flag: `DRAGONZPYDER_GOAL_STORE_ENABLED=1` (OFF by default).
Service identity: existing `DRAGONZPYDER_OPERLY_AGENT_TOKEN`.
Database: `DRAGONZPYDER_GOALS_DATABASE_URL`. Stored prompts are encrypted;
identities are domain-separated hashes. This does NOT execute jobs:
`job_registered=false` and `requires_fresh_authorization=true`
remain true. Do not interpret `next_run_at` as a Hatchet schedule.

**Operly wrapper:** `packages/workflow/dragonzpyder_goals.py`
forwards authenticated Personal/Workspace goal registration, read and cancel
requests to DragonZpyder. It does not start Operly's own AI agent or scheduler.
It is not yet exposed as a user-facing workflow capability.

**To safely complete the product:**
1. Complete a NEW DragonZpyder Personal identity, user-owned OAuth
   connection store and account migration; move Gmail/Calendar/Drive provider
   ownership and scopes, preserving explicit consent and token revocation.
2. Give DragonZpyder a local/remote computer broker with per-device consent,
   isolated process execution, visible approval for camera/microphone/screen,
   revocable permissions and no silent background sensor access. Keep Operly
   business sandboxes as authorized tool providers only.
3. Register Hatchet wakeups from DragonZpyder's durable goals and renew a
   single-job user/workspace delegation on each wake; do not persist Operly's
   240-second tool lease or an OAuth access token in a scheduled payload.
4. Add independent application principals for Operly and NaySchool, with
   separate secrets and contextual schemas. NaySchool learner data must not
   be accessible using an Operly service identity.
5. Move actual legacy workflow definitions/runs with checksums and read-back
   parity, then disable/retire Operly's old scheduler and custom planner only
   after a production-like staged canary proves resumed jobs, approvals,
   cancellation, idempotency and verified outcomes.

**Not release-ready:** Scheduled execution, automatic Gmail/calendar writes,
personal camera/computer access, NaySchool integration and migrating user
OAuth/data are explicitly NOT claimed as done by this PR.


## Durable Hatchet autonomy — synthetic-only acceptance slice

The previously missing **DB occurrence ledger + Hatchet worker bridge** has
been added, but remains OFF and undeployed. This is the first step toward
persistent autonomous goals, not authorization to use personal connectors.

- `goal_reconciler_schema.py`: unique goal/occurrence records, running leases,
  attempt counts, evidence digest and explicit failed/cancelled state.
- `goal_reconciler.py`: idempotent due-time scan, PostgreSQL row locking with
  `SKIP LOCKED`, ledger replay on duplicate/late Hatchet ticks, expired-claim
  recovery and bounded retries (max three attempts).
- `goal_tick.py` + `worker.py`: dedicated Hatchet worker task
  `dragonzpyder-goal-reconcile-v1`, 45-second execution timeout, concurrency 1,
  retry 1. Only a fixed internal canary principal may run DB-only code.
- `goal_tick_admin.py`: optional operator-only **staging** registration of
  exactly one durable Hatchet minute cron and one idempotent, recurring
  internal probe. Importing/starting a worker does NOT automatically create a
  cron.
- `goal_store.py` + `goal_router.py`: cancellation fences queued/running
  claims transactionally and authenticated owners can query recent receipts
  via `POST /internal/goals/runs`. External/user objectives remain unverified.

**Fail-closed flags:** `DRAGONZPYDER_GOAL_STORE_ENABLED=1`,
`DRAGONZPYDER_GOAL_TICK_ENABLED=1`,
`DRAGONZPYDER_GOAL_SYNTHETIC_ONLY=1`,
`DRAGONZPYDER_STAGE=staging`, and
`DRAGONZPYDER_GOAL_CRON_INSTALL_ALLOWED=1` (operator commands only).

Required secrets/config: `DRAGONZPYDER_GOALS_DATABASE_URL` (persistent
PostgreSQL, schema migrated), `DRAGONZPYDER_GOALS_ENCRYPTION_KEY` (valid
Fernet key, only in trusted service), and existing Hatchet worker
`HATCHET_CLIENT_TOKEN` + private host/TLS settings. Never pass model keys,
Operly OAuth tokens, or user-created leases to Hatchet inputs.

An operator deploying a dedicated staging worker can run once:

```sh
python -m agent_platform.goal_tick_admin install-cron
python -m agent_platform.goal_tick_admin seed-probe
```

The order is important: make sure the new task has registered with the Hatchet
server before provisioning its cron. Repeated cron installation is not
automatically treated as success; inspect Hatchet state for the fixed name.
A canary run records its result in `dragonzpyder_goal_runs`. A user's first due occurrence is recorded as `awaiting_authorization`; its
parent goal is paused with no further next-run time until genuine fresh
user consent is implemented. This prevents unbounded unauthorized cron
backlogs. User goals **are never executed** in this slice.
Neither fake permission grants nor cached 240-second Operly leases are used.

**Acceptance tests:** `api/tests/test_goal_recovery_postgres.py` simulates
restart, concurrent claim, late worker, replay, cancellation and tenant
isolation against real PostgreSQL. `hatchet_embedded_acceptance.py` executes
the real task twice via a disposable embedded Hatchet worker/engine and
asserts persisted evidence and zero user actions. The embedding test also
has a dedicated CI job.

**Next stage:** implement a scoped, durable per-goal consent record, fresh
permission lease on every Hatchet wake, budget reservation, bounded reasoning
plan and independent verifier before a scheduled job may invoke any Google,
MCP, desktop, camera, Operly Workspace or paid model capability.
