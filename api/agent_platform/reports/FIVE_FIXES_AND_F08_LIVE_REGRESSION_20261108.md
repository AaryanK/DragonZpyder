# DragonZpyder — Five long-horizon fixes and live regression (2026-11-08)

## Source and scope

- Repository: `AaryanK/DragonZpyder`, staging branch `chore/lean-platform-cleanup-20261107`, draft PR #33.
- Staging services: DragonZpyder Agent Test Lab and DragonZpyder Gateway Staging, Railway environment `staging`.
- Production was not merged or modified. Neither parent-level paid fan-out nor periodic paid benchmark runs are enabled after these trials.
- The API key keeps a provider-enforced **non-resetting cumulative $0.50 cap**.
- Prior Langfuse CSV exported from OpenRouter contained 129 model generations and 129 provider attempt spans. It was helpful for identifying F08's incorrect gradient-descent verifier criticism.
- Green CI is a software test result, not a long-horizon benchmark pass.

## Workstream 1 — Loop control and postfailure evidence

- `agent_platform/progress_guard.py` stops repeated identical tool action cycles and bounds supervisor AI turns; a new separate specialist guard stops delegated subagents after five AI turns.
- `AgentRuntime.run_report(..., recover_partial_on_failure=True)` reads LangGraph checkpoint state on recognized model-call/recursion/tool limits, preserves safe tool receipts and virtual paths, and returns `incomplete` rather than inventing success.
- `orchestration.py` excludes incomplete child reports from completed-track counts.
- **Verified:** Offline scripted real LangGraph graph tests, checkpoint recovery tests, and one real OpenRouter F08 retest.
- **Not proved:** The F08 retest still hit the full graph recursion limit. Specialist guard was added after that trial and has not yet been paid-model retested.

## Workstream 2 — Verifier confidence and numerical checks

- `agent_platform/scientific_oracles.py` provides bounded deterministic tools `check_quadratic_gradient_step` and `check_trilinear_interpolation` with finite-number validation.
- The supervisor and verifier are explicitly instructed to use numerical tools before treating a mathematical criticism as a mandatory rewrite.
- **Regression:** For quadratic `f'(x)=2x-20`, `x=5`, `learning_rate=0.1`, the correct update is `x_new=6`. The checker confirms the arithmetic and that the objective decreases. It differentiates that from a separate `+10` gradient problem.
- **Limit:** The checker only certifies its stated arithmetic; it is not a substitute for comprehensive code/scientific reviews, nor is there evidence that the specific checker was invoked by the live F08 agent.

## Workstream 3 — Isolated execution

- Staging has opt-in `langchain-quickjs` `CodeInterpreterMiddleware` backed by WebAssembly QuickJS, capped at 16MB, 2s per evaluation, four calls, no programmatic host tool bridges or subagents.
- `DRAGONZPYDER_AGENT_QUICKJS_ENABLED=1` enabled on the staging Test Lab.
- The offline test uses a scripted model and *actual* QuickJS tool execution to compute arithmetic and verify host `fetch` and `process` are not exposed.
- `scientific_oracles.py` supplies separate pure numerical validation.
- **Limit:** This is not a Python/OS/network/container sandbox; it cannot compile, run arbitrary Python repositories, or validate Geant4 end-to-end. Those capabilities need a separate isolated worker/microVM and acceptance tests.

## Workstream 4 — Gateway-authenticated parallel budgets

- `budget_reservations.py` supplies PostgreSQL atomic parent reservation and settlement, with concurrency/restart tests.
- New `gateway_parent_budget.py` supports an authenticated staging parent budget and conservative per-inference cost reservation. The gateway reserves before OpenRouter dispatch and settles only against reported provider cost. Missing/ambiguous/cost-over-cap outcomes retain their hold.
- `main.py` now exposes a service-authenticated `/internal/agent/v1/parallel-budget` endpoint and accepts `X-DragonZpyder-Parent-Job-Id` on approved agent inference. Budget use is bound to the real gateway and to provider routing price ceilings.
- `AgentRuntime.run_parallel_report` creates one parent job and routes two or three isolated child LangGraph tracks through it when all operator flags are enabled.
- Staging gateway database initialization logged `Staging atomic parent-budget gateway status=ready` at 19:19:59 UTC, after explicit opt-in to reuse the staging gateway usage PostgreSQL cluster.
- Tests cover FastAPI authenticated reservation-before-provider order, provider-cost settlement, real PostgreSQL atomic concurrency/restarts and no-cost LangGraph child overlap.
- **Still gated:** `DRAGONZPYDER_AGENT_PARALLEL_EVAL_ENABLED=0`, paid eval flags off. No matched real paid parallel-fan-out budget/settlement/timeout trial yet. The provider's own $0.50 cap remains ultimate aggregate protection.

## Workstream 5 — Provider rate control

- `provider_pacing.py` imposes a local gateway concurrency bound of 2 and 0.4s separation of agent requests. It parses and bounds `Retry-After` headers and applies a cooldown after upstream HTTP 429, with safe response propagation.
- Network/timeout/ambiguous 5xx outcomes are not automatically replayed as paid calls.
- The new F08 trial logged 24 successful gateway HTTP 200 agent requests and no 429 within that observed window.
- **Limit:** Pacing is per gateway process, not a distributed per-provider quota across replicas. It mitigates, but does not guarantee elimination of, provider-side throttling.

## Real F08 regression — after first wave of fixes, before specialist guard

Run key: `frontier-progress-guard-f08-20261108-v4`, November 8, 2026, 19:21:55–19:22:55 UTC.

| Metric | Observed |
|---|---|
| Real model | OpenRouter-backed |
| Agent elapsed | 60.93 seconds |
| Successful tools preserved | 12 |
| Completed delegated calls | 4 |
| Measured specialist overlap | True |
| Requested virtual artifacts created | 3 |
| Verified artifact readbacks | 0 |
| Termination | `graph_recursion_limit` |
| Checkpoint recovered | True |
| Outcome | `execution_incomplete`; objective not verified |
| Provider key balance delta | approx $0.0538885 |
| Approx key allowance before run | $0.14672476 |

The regression is a **partial diagnostic improvement**, not a long-horizon pass. This run still reached the recursion limit. The checkpoint recovery did preserve meaningful execution evidence instead of reporting zero tools. Follow-up mitigation adds specialist-specific limits, but was not subjected to another paid run.

## Next verified gates

1. Check that specialist stopping yields explicit incomplete receipts in real model execution and reduces recurring verifier/tool cycles.
2. Measure whether the F08 numerical checker is actually invoked, and whether false positive verifier corrections decline.
3. Require every expected artifact's independent readback and a case-specific outcome oracle; virtual files are not scientific proof.
4. Run a low-ceiling, opt-in, paid multi-child budget integration trial across actual gateway inference with replay, unknown-cost and failover conditions before claiming production-grade parallel execution.
5. Implement provider-wide distributed pacing if multiple gateway replicas become active; correlate model generations and cost to individual agent runs in Langfuse once staged credentials are configured.
