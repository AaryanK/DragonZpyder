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
