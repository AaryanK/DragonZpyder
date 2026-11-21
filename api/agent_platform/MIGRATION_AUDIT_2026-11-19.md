# DragonZpyder / Operly agent infrastructure consolidation — 19 Nov 2026

**Status:** migration slice, draft review only. No deployment, paid inference, third-party MCP access, or user-data migration.

## Code inventory / ownership

| Area | DragonZpyder staging (PR #33) | Operly main / open PR #373 | Decision |
| --- | --- | --- | --- |
| Agent reasoning | Deep Agents / LangGraph, bounded specialists, virtual filesystem, PostgreSQL checkpoint | Custom governed agent loop; draft delegation to DragonZpyder | DragonZpyder canonical supervisor; keep Operly fallback until parity |
| Persistence | Agent checkpointing; Hatchet ping + bounded 5-minute agent task | PostgreSQL-backed leased workflow scheduler, retries, approval and waits | Hatchet control plane + durable goal ledger in DragonZpyder; do not deploy overlapping schedulers |
| Durable goals | Synthetic cron demonstrated in PR #33; owner-scoped goal/recovery code exists in **unmerged PR #37**, not this base | PR #373 forwards goal registration without starting jobs | Reconcile PR #37, test restart/cancel/replay and renewed authority before exposing recurring user jobs |
| Tool access | Virtual tools and unbound Operly signed sandbox adapter | Kernel, permission checks, audited capability registry, inbound MCP OAuth | Operly remains enforcement authority for business side effects; DragonZpyder owns tool discovery |
| Remote MCP | Not present on this staging base before this PR | Operly inbound MCP provider | This PR ports *offline* reviewed capability hub and remote MCP client adapter from PR #37 |
| Credentials/local devices | Personal OIDC core is staged, still disabled; no desktop executor | Business-scoped provider credentials and sandbox | Do not migrate passwords or OAuth tokens to prompts or generic MCP servers. Local vault and per-device consent are future work |
| Privacy and accounting | Gateway budget reservations, partial Mem0 testing | Scope-aware budgets and provider guards | Require atomic per-task + parent spend reconciliation, retention/erasure tests, and revocation checks |

## Delivered by this PR

- Per-run **CapabilityHub** with duplicate-name rejection, bounded tool count, classified provider/risk and no user-controlled registration interface.
- Experimental **ApprovedMCPServer** adapter, ported from PR #37. Explicit reviewed host, reviewed tool allowlist, HTTPS, tool name prefix, refusal of user-provided origins, opt-in flags and declared egress firewall.
- Offline safety tests and opt-in MCP client dependency included in agent-stack CI.
- No injection into the public AgentRuntime or web app. No live endpoints or token/OAuth broker.

## Must happen before real autonomous long-running work

1. Consolidate PR #37 goal ledger and task UI against the current PR #33 head; PR #37 was written against an older base and is not mergeable as-is.
2. Connect Hatchet wakeups to **durable owner-scoped goals**; explicitly renew the permitted user/workspace authority on every wake. Long-lived user goals must not persist short-lived Operly leases.
3. Add independently verified completion receipts, retries with external mutation idempotency, cancellation fencing, human approval pauses and recovery after worker restart.
4. Add a local computer node with OS keychain-backed credentials and user-controlled permission grants. Cloud models see only the authorized minimized context; local-model classification is not itself a security boundary.
5. Integrate the capability hub with the harness only after a real outbound MCP authorization broker exists, DNS/egress enforcement is verified and tool outputs are treated as untrusted.
6. Reconcile Operly PR #373 and run cross-repo scoped delegation tests. Keep Operly Kernel, business memberships, approval and audit as the authority.
7. Validate both offline and in isolated staging: no paid-model calls by default, no unapproved side effects, bounded spend, owner isolation, repeated/cancelled/failed jobs and actual resulting artifacts.

## Safety boundary

A persistent *schedule* does not imply permission to execute arbitrary actions. Both the source of credentials and the ability to authorize an action remain outside the LLM. No production flags are turned on by this source-only change.

## Next phase (local-first design research)

Measure an edge model for tool selection and personal-context minimization; use a secure vault/keychain and deterministic policy enforcement. Treat cloud consultation as an explicitly consented disclosure rather than claiming perfect anonymization (content can itself identify its source).

References:
- DragonZpyder PR #33: https://github.com/AaryanK/DragonZpyder/pull/33
- DragonZpyder PR #37: https://github.com/AaryanK/DragonZpyder/pull/37
- Operly PR #373: https://github.com/AaryanK/Operly/pull/373
