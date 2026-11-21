# DragonZpyder personal AI capability contract

**One personal user identity, shared context, model-independent harness, metered execution.**
Operly is the organizational/workspace layer. It delegates bounded capabilities to
DragonZpyder but remains the authority for its own membership, files and approvals.

## Architecture (reuse instead of rebuild)

| Capability | Existing/open-source component | Stage |
| --- | --- | --- |
| General personal chat and model routing | DragonZpyder gateway + OpenRouter catalog + daily budget | Added; OIDC gate remains closed |
| Long-running agent loop, planning and handoffs | Deep Agents + LangGraph checkpoints | Existing staging smoke verified |
| Scheduled jobs, delays and cron | Hatchet | Ping and 20-second delayed execution verified |
| Personal memory | Mem0 + Postgres/pgvector | Synthetic write/search/delete verified; history erasure pending |
| Tool traces and run evaluation | Langfuse | Existing SDK adapters; staging keys/trace validation pending |
| Personal browser/computer | Provider adapter and isolated sandbox computer | Not granted to personal users yet |
| External apps and services | MCP and signed capability registry | No personal delegation yet |
| Files and artifact production | Isolated filesystem and sandbox with result verification | Read-only virtual files in present staging harness |
| Multi-agent teams | Deep Agents subagents + Hatchet task DAG, budgets per child | Work remaining |
| Voice, images, audio/video, mobile nodes | Modality-specific adapters through shared policies | Work remaining |
| Local inference and BYOK | OpenAI-compatible model/provider adapter | Work remaining |

## Lowest-cost execution strategy

1. No computer or agent process for an ordinary direct answer; only a metered model call.
2. Route by task requirements and an operator-reviewed quality/cost allowlist.
   Use live prices with a hard provider-side max_price cap. Default to affordable
   models and promote to stronger models only after verification detects insufficiency
   or users request more reasoning.
3. Keep prompt context short: retrieval first, compact/offload long tool output,
   use versioned skills rather than sending full tool descriptions on every call.
4. Run sandbox computers only while executing; pause/terminate after completion.
   Share saved artifacts, not a permanently warm VM for every user.
5. Use Hatchet for waiting, cron and retries; do not run model tokens while sleeping.
6. Per-identity/day and per-task cost reservations, concurrency caps, immutable
   accounting and user-visible spend history. Unknown costs do not become zero.
7. User may opt into local execution/BYOK when implemented, without granting
   cloud access to local private data by default.

## Safety and authorization are capabilities too

The goal is no **arbitrary paywall feature restrictions**, not anonymous/unlimited
third-party compute or unrestricted access to accounts. Every external action
must have a specific capability lease, verified principal, environment
isolation, time/step/spend ceiling, audit trace and approval where appropriate.
Delegation to Operly MUST be signed and rechecked by Operly.
Never store user credentials inside model prompts or unencrypted memory.
User consent and complete deletion semantics are required before personal memory.

## Minimum acceptance scenario before inviting real users

1. User signs in with scoped OIDC access token.
2. User asks an ordinary question; cheap catalog-approved model answers through
   the shared DragonZpyder metered gateway with accurate spend reporting.
3. User initiates a scheduled read-only research task; Hatchet persists it,
   Deep Agents resumes and returns an artifact, with Langfuse traces and budget.
4. User delegates a browser/computer task; sandbox runs with a short-lived
   capability and the user can review/approve side effects.
5. Tests verify that one user's history, spending, memory, computer and app
   authority cannot be accessed by another; cancellation, recovery, deletion
   and provider failures are handled correctly.

Only the first two are partially implemented at this point; OIDC issuer
provisioning is still outstanding. Do not label the wider product launched.
