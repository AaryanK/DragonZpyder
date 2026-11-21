# Universal tool runtime — DragonZpyder engineering decision (2026-11-21)

## Goal

An authorized MCP tool must be callable by the same agent in chat or after a
scheduled wake. Adding another provider must not require editing Hatchet's
worker, rewriting a scheduler, or widening user permissions.

## Actual Railway production inventory

- DragonZpyder API and worker, Hatchet, and PostgreSQL are deployed.
- The API initializes LangGraph PostgreSQL checkpoints.
- Langfuse credentials exist but current runtime.py telemetry_callbacks traces
  only explicitly opted-in synthetic staging evaluations. Production Personal
  agent tracing is **not independently verified**.
- No Temporal service or Temporal environment-variable names appeared in the
  inspected Railway production projects. Do not add Temporal just to duplicate
  Hatchet.
- Operly Personal session renewal issues scoped, short-lived MCP tool grants.

## System responsibility boundaries

| System | Responsibility |
| --- | --- |
| DragonZpyder Deep Agents | Reason, choose authorized tools, resume objective |
| MCP broker | Trusted provider origin, discovery, alias mapping, guarded invocation |
| Operly / other connectors | Live signed identity, provider-specific auth, capability grants |
| LangGraph + PostgreSQL | Agent checkpoint and durable goal/effect ledger |
| Hatchet | Schedule future work, dispatch one durable execution |
| Langfuse/OTel | Redacted tool/model tracing and evaluation, not authorization |

## Shared MCP tool binding

Every trusted provider connector supplies a provider ID, vetted URL, current
credential headers, and the exact tool-ID allowlist issued by that provider.
The model never supplies a URL, credential or additional grant.

The broker uses the upstream MCP SDK and LangChain-adapted tools. Agent-facing
names have a stable provider prefix. The underlying adapter still calls the
original provider capability ID.

External tool execution validates the exact approved capability, argument
schema and size, plus an unattended-execution risk policy before calling
the SDK's asynchronous invoke. Receipt records include a stable tool alias,
input/result hashes and status, never bearer tokens.

MCP annotations such as readOnlyHint are informative but not a substitute for
trusted user authority or explicit unattended-execution policy.

## Wake algorithm

1. Hatchet dispatches goal ID and sequence, not raw provider credentials.
2. Load durable goal/plan and verify the current user, sequence, budget and
   authorization requirements.
3. Renew provider authorization and rediscover current tool capabilities.
4. Validate the exact capability and arguments against the current schema.
5. Record an execution fence before the external side effect.
6. Call the same MCP tool adapter used in live chat.
7. Verify provider response, checkpoint, record protected result or digest,
   and select the next scheduled step.
8. On revocation or denial, block; never substitute a different tool.
9. On uncertain write outcome, never retry without safe idempotency/readback.

A successful Hatchet task or HTTP 200 is *not* a successful external tool
call. Exactly-once external effects are not automatically guaranteed: use
provider idempotency keys and distinguish at-least-once scheduling from
effectively-once side effects.

## Phased implementation

### Phase 1 — PR #94

Provider-neutral MCP discovery and invocation, collision-safe aliases,
per-run scope checks and verified tool receipts. The existing Operly MCP
connector becomes a thin provider adapter. No change to Hatchet or Operly.

### Phase 2 — not included in phase 1

Persist a typed execution plan, including provider ID, exact capability ID,
validated input arguments, risk class, approvals, cadence and budget. The
scheduler reads goal ID and resumes the plan, with no hardcoded capability
selection in personal_wake.py.

### Phase 3 — not included in phase 1

Put all interactive and scheduled tool calls behind shared invocation/receipt
middleware. Add a durable scheduling outbox, approval/resume path and
reconciler. Correlate redacted Langfuse/OTel spans to step and goal IDs
without logging personal data or credentials.

### Phase 4 — final proof

Attach a second independent, authenticated MCP provider through the same
broker. Show that Hatchet needs no code changes. Test read-only, approval,
revocation, worker restart, unknown tool failure and cost exhaustion.

## Live acceptance gate

An end-to-end pass requires five separate wake-ups approximately two minutes
apart, five actual provider tool receipts, persisted checkpoints and protected
results, no duplicate effects, honest goal_status output and a final user
report. Mocked test passes and scheduling acknowledgements do not count.

## Public reference contracts

- LangChain MCP client: https://reference.langchain.com/python/langchain-mcp-adapters/client/MultiServerMCPClient
- LangGraph durable execution: https://docs.langchain.com/oss/python/langgraph/durable-execution
- Hatchet scheduling: https://docs.hatchet.run/reference/python/runnables
- Temporal activities and idempotency: https://docs.temporal.io/activity-definition
- Langfuse MCP trace propagation: https://langfuse.com/docs/observability/features/mcp-tracing
