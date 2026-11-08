# DragonZpyder — real-model long-horizon evaluation, November 8, 2026

## Scope and reproducibility

- **Environment:** Railway project `DRAGONZPYDER AGENT STAGING`, environment `staging`; production untouched.
- **Repository:** `AaryanK/DragonZpyder`, branch `chore/lean-platform-cleanup-20261107`.
- **Fixture:** `api/agent_platform/evals/frontier_stress_v1.json`, ten original 450+ word prompts spanning independent domains. The model received each full prompt, not simplified sample substitutes.
- **Model route:** authenticated private staging gateway to OpenRouter with a verified non-resetting **$0.50 upstream per-key cap**; no direct inference, shell/computer, or external side-effect tools.
- **Evidence policy:** no outcome is called complete without independent environment-state tests/oracle, artifact write-and-read evidence, required capabilities, and measured specialist overlap.
- **Important:** These tests are not matched trials against Claude Code, Codex or other frontier agents. Offline CI passes do not count as task success.

## Round 1: ten distinct live case attempts

| Case | Scenario | Observed execution outcome | Seconds | Fully verified |
|---|---|---|---:|---|
| F01 | Distributed checkout repair | `ModelCallLimitExceededError` | 11.24 | No |
| F02 | Magnetic-field interpolation audit | `ModelCallLimitExceededError` | 15.20 | No |
| F03 | Public guidelines conflict synthesis | Provider HTTP `429` rate limit | 5.06 | No |
| F04 | Three-ledger close audit | `GraphRecursionError` | 17.37 | No |
| F05 | Archival manuscript provenance | Provider HTTP `429` rate limit | 1.16 | No |
| F06 | Cross-border travel recovery | Provider HTTP `429` rate limit | 0.83 | No |
| F07 | Permission-leak containment | `ModelCallLimitExceededError` | 18.85 | No |
| F08 | Adaptive education design | `GraphRecursionError` | 12.81 | No |
| F09 | Regional outage drill | `ModelCallLimitExceededError` | 12.62 | No |
| F10 | Multi-day Nepal monitoring and publication | Provider HTTP `429` rate limit | 0.84 | No |

F07 was executed in the durable run `frontier-ten-20261108-real-v1`, which stopped at its first failure. The remaining nine were executed in `frontier-nine-20261108-real-v2`. The rate-limited cases are **attempts, not meaningful complete model evaluations**. For executions raising an exception, the evaluator did not recover partial checkpoint/tool evidence; a `tools=0` diagnostic means no verified completed-tool count was retained, not necessarily that the model never called tools. All runs occurred under the provider key cap.

## Round 2: bounded stress-mode expansion

Commit `57f83b43206b8b0c4e580d82892b1f3e7f4d3af3` changed **paid staging stress mode only**: supervisor call limit 12 → 24; specialist limit 5 → 7; recursion ceiling 32 → 96; task delegations 3 → 4. The runner used a provider cooldown and independent run key `frontier-improved-20261108-real-v3`. No durable parent-level paid parallel fan-out was enabled.

| Case | Result | Seconds | Observed evidence | Full objective |
|---|---|---:|---|---|
| F08 | `GraphRecursionError` | 70.00 | 26 successful HTTP 200 gateway inference requests observed; no final artifact report due graph exception | Not verified |
| F02 | `capability_blocked` (agent run returned) | 60.92 | 14 successful agent tools; 3 delegated calls; measured overlapping inline specialist spans; all three named virtual artifacts created, only one read-back verified | Not verified |

**F02** demonstrated genuine concurrent inline specialist delegation and a virtual-artifact workflow. It did **not** validate magnetic-field mathematics with an executable test harness, prove external parent-level parallel fan-out, verify every artifact's contents, or pass the independent outcome oracle. Required `sandbox` and `parallel_subagents` capabilities are still absent from the evaluator's verified capability set. F08 continuing to recurse after much larger limits indicates a planning/termination failure rather than a cap that can safely be raised indefinitely.

## Spending

At baseline start the provider gateway reported `$0.45552846` remaining under the total `$0.50` key cap. At the end of the F02 improved trial the runner reported about `$0.17277681` remaining. The observed **key-balance delta of about $0.28275** spans this evaluation window and may include other traffic using the same key and delayed provider accounting. It is **not** a per-case invoice or proof of attributable charges. The provider's hard key ceiling remained in force. Testing flags were subsequently switched off.

## Conclusions and prioritized next engineering work

1. **Prevent agent cycles:** instrument checkpoint-recoverable tool/call traces on graph exceptions; detect repeated planning/delegation loops, enforce progress checks, and terminate with a truthful partial-state report rather than `GraphRecursionError` or `ModelCallLimitExceededError`.
2. **Add independently executable sandboxes:** numerical F02 oracle must test boundary interpolation, coordinate transforms, physics tolerances and exact expected outputs; F01/F07/F09 must apply patches inside isolated throwaway repositories/environments and run tests. Virtual files alone are insufficient.
3. **Provider resilience:** distinguish provider `429` limits from budget rejection, back off with controlled retries under an atomic reservation/usage ledger; do not hammer models in sequence.
4. **True parallel parent jobs:** connect the existing PostgreSQL `AtomicBudgetStore` primitive to the authenticated gateway for child-request reservations/settlement/replay before removing the guard in `AgentRuntime.run_parallel_report`. Inline overlapping subagent calls are not equivalent to resilient durable parallel fan-out.
5. **Benchmark parity:** only compare against frontier agents after replaying identical task fixtures in equivalent real environments, with objectively graded artifacts, actual task pass rates, comparable parallel spans, tool reliability, measured cost and wall time.

**Verdict:** 10/10 real cases attempted; 0/10 independent objectives verified in the first round. Two targeted paid retests produced one incomplete graph execution (F08) and one substantial, but still incomplete, tool/delegation/artifact result (F02). No frontier-parity claim is warranted.
