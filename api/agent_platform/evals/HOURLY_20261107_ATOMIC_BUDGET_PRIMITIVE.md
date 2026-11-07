# Hourly frontier engineering: transactional parent budget primitive

Date: 2026-11-07, 14:00 America/Chicago. Scope: draft PR #33 only.

## Starting state
- Default branch `master`; draft PR #33 base `codex/consolidate-dragonzpyder-web`.
- Head at start `2347b6273c3a5321c633457391bb90259daf95cc`, all three GitHub Actions workflows successful.
- Railway staging: eight services, no unresolved issues, no recent failed deployments and no pending changes; Personal Core sleeping. This is service health, **not** task success.
- Previous cycle disabled paid parallel fan-out pending an atomic parent budget. This cycle does not bypass that gate.

## Selected improvement
Created a reusable PostgreSQL transactional parent-child USD reservation primitive, not yet wired to paid inference:
- `api/agent_platform/budget_reservations.py`: schema for parent ceiling/reserved/settled totals and unique request-ID reservations; strictly bounded decimal USD inputs; canonical UUIDs; parent-row `SELECT ... FOR UPDATE` before checking/reserving budget; idempotent replay detection; settlement moves the held estimate into actual settled cost and frees the difference. Unknown or over-reservation cost retains the hold and fails closed.
- `api/tests/test_budget_reservations.py`: offline validation of invalid/overprecision amounts, UUIDs, schema constraints, replay conflicts, parent ceiling, unknown-cost hold, exact settlement and zero-cost settlement.
- `.github/workflows/dragonzpyder-api.yml`: include the new offline contracts in the agent-stack test job.

## Commits
- `40edb02979fc7c5385733f899e41dd1bb8f72657`: initial primitive.
- `dd87de6c30d44a516aadc1d3611c9a2c2c552041`: correct unknown-cost rollback/hold behavior and zero-cost settlements.
- `32393e359cb0932d2e32f7d94c48fd65ce41061c`: offline safety contracts.
- `5accac0792adf6345563cdce6bd9e0ffda61df8b`: CI test wiring.
- API CI: https://github.com/AaryanK/DragonZpyder/actions/runs/42409317964 (in progress at initial report creation).

## Verification limits and next action
The new module is **not wired to the live gateway**. The tests use a deterministic fake database and do **not** establish real PostgreSQL locking, crash safety, authorization or inference cost accuracy. No paid model trial, independently verified frontier completion, production merge, deployment or new external capability was performed.

Next: identify the actual gateway ingress and authenticated job context, add real PostgreSQL concurrency/restart/rollback integration tests (including competing child reservations), and enforce upper-bound per-model provider price estimates at the gateway. Require an explicit reviewed deployment/approval before turning paid fan-out back on. A model that reports unknown cost must retain a hold; a retry must not duplicate paid inference. Frontier parity is unverified.
