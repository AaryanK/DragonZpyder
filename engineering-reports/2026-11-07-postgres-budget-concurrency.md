# DragonZpyder frontier engineering — real PostgreSQL budget concurrency verification

**Date:** 2026-11-07 15:00 America/Chicago. **Scope:** draft PR #33, no production deployment.

## Starting state

- Default branch `master`, PR #33 open and draft on `chore/lean-platform-cleanup-20261107`.
- Previous budget reservation primitive was offline-fake-tested only; paid parallel inference remains explicitly blocked.
- Railway staging: eight services, seven online and Personal Core sleeping; zero warnings/critical issues or recent failures; no pending deployment. This does **not** certify agent-task success.
- Existing code enforces parent-row locking, idempotent reservation and settlement, but no real PostgreSQL concurrent/restart test existed.

## Change

Added `api/tests/test_budget_postgres_integration.py` with two real-database contracts:
1. Eight concurrently attempted child reservations for the same one-dollar parent ceiling, each requesting USD 0.30, must yield exactly three reservations and five denials. Confirm parent counters, re-created store object, replay prevention, unknown-cost hold retention, settlement idempotence/conflict rejection, and exactly one additional reservation after settlement releases capacity.
2. Confirm conflicting ceiling replays, cross-tenant job access and settlement attempts fail closed.

Each test creates a fresh randomized PostgreSQL schema, uses multiple independent pool connections, and drops the schema in `finally`. No paid model calls, user data, or staging database writes.

Updated `.github/workflows/dragonzpyder-api.yml` with a separate `budget-postgres-integration` job, using an ephemeral PostgreSQL 16 GitHub Actions service and test-only credentials.

## Verified evidence

- Implementation commit `fe15d5e968592f46e139c3e382c0a2e1106bef6a`.
- CI wiring commit `dcecd98e63736a39a8c7440ddeaaf5b4a68031bd`.
- API workflow: https://github.com/AaryanK/DragonZpyder/actions/runs/42414184368
- `budget-postgres-integration`: **2 passed in 0.60s** against actual PostgreSQL, job success.
- `fastapi-contract`, `personal-core-contracts`, and `legacy-compatibility` jobs succeeded; agent-stack job was still in progress when the report was prepared.
- No external frontier benchmark runs or paid model inference this cycle. Frontier parity **not established**.

## Remaining gaps and next action

The reservation store is still **not connected to the authenticated gateway**; the real-DB tests validate transaction behavior only. There is no verified gateway-side binding of tenant/job identity, model-price upper-bound estimation, retry deduplication or crash recovery for actual inference. Paid parallel fan-out must remain blocked. Next: inspect gateway request path and enforce server-side identity and reservation for each child request, then test unknown provider costs and retry behavior with a safe fake upstream, followed by explicit-approval bounded real-model trials.

No production merge, secrets change, destructive operation or permission expansion was performed.
