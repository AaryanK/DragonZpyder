# Hourly engineering: durable unknown-cost holds

**Date:** 2026-11-07 15:56 America/Chicago. **Scope:** draft PR #33 only; no production merge/deploy, no paid inference.

## Starting state and independent checks

- Repository default branch: `master`; PR #33 open, draft, mergeable, staging branch `chore/lean-platform-cleanup-20261107`.
- Prior PR head `ff34ecf3a4a964a72de31264663aae02304fb194` had a real PostgreSQL budget test report, but gateway enforcement remains unwired.
- Railway staging: eight services (seven online, Personal Core sleeping), zero recent failures, no pending work. This does not establish agent task success.
- The shared-budget primitive held money when a provider cost was missing or exceeded its reservation. However, it **raised inside a PostgreSQL transaction without recording the unresolved state**. Its schema already declared a status `unknown`, but no code wrote that status. An operator could not reliably distinguish a still-in-flight reservation from an unresolved post-dispatch outcome after a crash.

## Bounded change

In `api/agent_platform/budget_reservations.py`, `settle()` now writes `status='unknown'` when cost is missing or above estimate, commits that transition while leaving the full USD hold intact, and **only then raises** `BudgetExceeded`. A later authenticated reconciliation with a known cost within the original estimate can settle once; a replay cannot re-dispatch inference. No hold is silently released.

Updated `api/tests/test_budget_reservations.py` to assert durable unknown status in the fake connection and `api/tests/test_budget_postgres_integration.py` to check that real PostgreSQL persists `unknown` with null actual cost and unchanged parent counters across a new store instance, before reconciliation.

Implementation commits:
- `5111d2b27d88fbd49b4507dca4dbfd6f7bf838ff`
- `6becde637d88a3235b09ba4904d0ba3f59f85365`
- `6e96748f38b16b5bc514cd03b6e0e94b15d2228c`

## Verification boundary

CI launched for `6e96748f38b16b5bc514cd03b6e0e94b15d2228c`: https://github.com/AaryanK/DragonZpyder/actions/runs/42418266957 . Results must be checked before treating the new tests as passed. The change affects only a currently **unwired** budget primitive. No real paid model, gateway dispatch, model-provider billing reconciliation, or frontier comparison was executed this cycle.

## Next highest-impact gate

Integrate authenticated tenant/job identity and atomic budget reservations **inside the actual gateway** before each paid child request. Validate immutable request IDs, maximum provider price, actual usage-cost settlement, unknown/timeout holds and replay handling with a fake upstream and real PostgreSQL. Keep paid fan-out disabled until those end-to-end tests pass. Then run strictly bounded live tool-call smoke and independent artifact/environment oracles; track verified completions, latency, cost, false successes and interventions. Frontier parity remains unverified.
