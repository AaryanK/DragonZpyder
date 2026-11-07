# DragonZpyder frontier engineering: paid fan-out safety gate

Date: 2026-11-07 (13:00 America/Chicago). Scope: staging draft PR #33 only.

## Starting state
- Repository default branch: `master`; PR #33 base:
  `codex/consolidate-dragonzpyder-web`; head at inspection:
  `46bb7d62ce11b4b41492f3c2926ef006d3896cef`.
- All three GitHub workflow families for that head were successful.
- Railway staging: 8 services, 0 recent failures, 0 unresolved
  warnings, 0 pending changes; Personal Core sleeping. Health is not
  proof of agent success.
- Previous iteration fixed specialist builder model routing. No repeat.

## Independently inspectable finding
`AgentRuntime.run_parallel_report` previously allowed real paid
multi-child model execution if six feature flags were set. Each child
started a separate runtime and checkpoint connection, but there was
**no atomic parent USD budget reservation**. The gateway's existing
per-request throttling and usage ledger are not a shared task budget.
Two or three concurrent children can spend independently before
usage accounting is persisted; retries, unknown usage and cancellation
make post-hoc sums insufficient. Feature flags are not a substitute
for a transactional, authenticated gateway enforcement point.

## Narrow change
- `api/agent_platform/runtime.py`: fail closed before any child is
  spawned, even with all paid evaluation flags enabled. The error
  explicitly states that atomic shared gateway budget enforcement is
  missing. Remove the unreachable paid fan-out path rather than
  retaining an apparently available unsafe code path.
- `api/tests/test_harness_v2.py`: add regression checks with all
  flags enabled, plus an attacker/operator-supplied
  `DRAGONZPYDER_AGENT_SHARED_BUDGET_ENFORCED=1` assertion; neither
  can bypass the guard. No network or model call is made.
- Offline `orchestration.py` fan-out remains available for real
  LangGraph execution with scripted models and measured overlap.
  Single-agent metered gateway operation is unchanged.
- This is a security/cost-containment improvement, **not** a claim
  that atomic budgets have been implemented or that parallel
  frontier-agent performance has improved.

## Commits
- `790e7f7be7aaf3c7bef6e530e6fc726aded830e6`
- `c9875e6ebaa9e36f1d6d5d39c3e77a3f61ce70f8`
- `525a0d805e828aadba0facaeefcdb88399f710c0`

## Acceptance and next work
Verify the latest PR head's GitHub Actions status, especially the
agent-stack test job. The tests are offline behavioral checks, not
proof of live budget enforcement. No paid model calls, production
merges, deployments, new permissions, secrets, or external actions.

Next: implement a database-transactional parent job budget at the
**gateway** (not in agent-only Python), with idempotent per-request
reservations, upper-bound cost estimates, concurrent child locking,
reconciliation of actual provider cost, unknown-cost hold,
retry/cancellation recovery, and crash/restart tests. Only then
re-enable real parallel trials under explicit operator-approved
dollar ceilings. Frontier parity remains unverified: zero real
independently judged long-horizon completions this cycle.
