# Bounded Hatchet Personal Goal Controller (opt-in)

This is a fail-closed **read-only Personal MCP** orchestration slice, not a general autonomous goal manager. The existing `dragonzpyder-personal-mcp-wake` Hatchet task, PostgreSQL `dz_personal_mcp_goals` and `dz_personal_mcp_receipts`, and Operly's live-session renewal remain authoritative.

## Execution contract

- `dragonzpyder-personal-goal-controller` accepts an operator-authorized, immutable `PersonalGoalPlanInput` (2–3 sequential wakes). It **does not** expose a user-facing creation API, generate crons, or trigger a run by registering a worker.
- Every wake revalidates the original Personal user/session, obtains a fresh scoped MCP token from Operly, and then runs the same user/conversation LangGraph thread. The existing MCP mutation gate must remain off.
- PostgreSQL row locking fences each goal/sequence. Completed wake receipts persist. A re-dispatched plan skips already committed steps; terminal states stop the controller. This is *receipt-level deduplication*, not a guarantee of exactly-once network effects during ambiguous failures.
- A known internal inference 429 (or checkpointed incomplete quota stop) records `paused_budget` and keeps the sequence unchanged. No further wake is sent. A duplicate Hatchet dispatch cannot restart the paused step.
- `operator_resume_paused_personal_goal` is an internal **operator-only** helper behind `DRAGONZPYDER_PERSONAL_MCP_RESUME_OPERATOR_ALLOWED=1`. It renews the original Personal session and checks immutable goal identity, objective hash and sequence before marking the goal active. It does **not** enqueue a new run. An independently authorized caller must explicitly dispatch Hatchet again.
- Revoked authority yields `blocked`. Missing DB, invalid backend configuration, unexpected provider failures and ambiguous effects fail closed. Never retry unknown external actions automatically.

## Flags / deployment

Default: none of the new flags is enabled. Existing prerequisites remain mandatory: `DRAGONZPYDER_PERSONAL_MCP_SCHEDULED_ENABLED=1`, valid dedicated worker, Hatchet connectivity, read-only MCP, immutable HTTPS service endpoints, trusted backend secrets, and initialized PostgreSQL schema.

- `DRAGONZPYDER_PERSONAL_GOAL_CONTROLLER_ENABLED=1`: registers the bounded controller **on a dedicated worker only**.
- `DRAGONZPYDER_PERSONAL_MCP_RESUME_OPERATOR_ALLOWED=1`: permits *internal* operator resume, not public chat/user-triggered resumes.

Registering either task does not create schedules or authenticate any model-chosen user identity. Before enabling production, provision/verify the schema, require a trusted per-user goal submission and approval endpoint, propagate authenticated cancellation, establish a per-goal atomic USD budget and test a live end-to-end Hatchet wake, worker restart, session revocation, and ambiguous provider failure.

## Verification

Unit tests: `api/tests/test_personal_mcp_wake.py`.
PostgreSQL real-DB integration tests with **simulated** external HTTP: `api/tests/test_personal_mcp_wake_postgres.py`.

These prove persistence, state fencing, and credential-renewal request shape, **not** production scheduling success, cost allocation, real MCP effects, or independent objective correctness.
