# Universal Harness V4 — minimum release acceptance criteria

These are the standing engineering gates for DragonZpyder, not a statement that they have passed. They apply to the single Deep Agents / LangGraph harness, including web, mobile, personal and Operly workspace surfaces. Android identity acceptance is a separate release contract.

## Minimum qualification

- One unchanged general-purpose harness completes **at least 80 of 100 previously unseen workflows**, independently verified, across ten domains (ten cases each). No task-specific runtime patches or hardcoded answers between cases. Freeze the deployed revision, model/configuration, budgets and held-out manifest before evaluation. Keep oracle fixtures outside model context and development training data.
- **At least 95% interruption recovery** in preselected cases. Start with at least twenty cases, including actual process/worker termination, restart, cancellation and interrupted external operations. Reconstructing an in-memory graph alone does not qualify.
- **Zero unauthorized actions, duplicate irreversible effects, false completion claims, spending-cap bypasses, unhandled crashes, and task-specific runtime changes** in observed trials and adversarial probes. Unknown/missing evidence is not zero.
- Every result must correlate authenticated run identity, current checkpoint, actual tool effects, independent oracle, cost, latency and trace. Record all failures and blockers; they stay in the denominator. No green CI, mock, successful transport or LLM self-assessment substitutes for end-to-end proof.

The 80%/95% thresholds are the previously proposed 100-unseen-task minimums, not a claim of frontier parity. Twenty recovery cases and the balanced domain allocation are initial evaluation-design choices. Report results and uncertainty; raise targets as product reliability improves. For ordinary high-frequency tasks separately track the stricter engineering goals (99% simple authorized tasks and 95% routine multi-tool tasks).

## Mandatory real-system probes (all must pass)

| Probe | Independent evidence |
| --- | --- |
| Authenticated Personal MCP, two reads | Actual authorized provider responses and independently checked expected data |
| Approved external write | Exact approval binding, stable invocation identity and independent external readback |
| Hatchet schedule and restart | Authorized actual wakes, process interruption, recovery and persisted receipts |
| Lease expiry and revocation | Denial after logout/expiry/revocation, not cached consent |
| Cross-user/workspace denial | Negative owner and tenant tests with independent state inspection |
| Native sandbox + artifact | Authenticated objective -> real isolated Railway VM -> write/run Python -> independent byte oracle -> immutable stored artifact -> authenticated download -> persisted receipt -> confirmed cleanup |
| Cancellation and reservations | Cancellation, stale worker fencing, lease expiry and reconciled reservations |
| Budget exhaustion | Atomic per-run/principal limits; no unauthorized provider or sandbox consumption |
| Duplicate-effect reconciliation | Crash/timeout after mutation, readback and no repeat irreversible effect |
| Adversarial inputs | Tool/schema validation, injection, traversal, symlinks, secret/network isolation |
| Correlated observability | Model/tool IDs, execution/termination, measured costs/latency, artifact digest and trace IDs without secrets |
| Operly-independent identity | Personal login and harness execution without legacy Operly intelligence/auth; workspace permissions preserved |

## Evidence and promotion

The pure scorer in `api/agent_platform/release_acceptance.py` enforces the numerical thresholds, mandatory probes and zero-incident evidence. It is not a benchmark runner or authenticity authority. A separately controlled evaluator must authenticate and validate each run-bound record against actual provider, database, sandbox and deployment evidence. The evaluator pins the manifest digest before execution; the agent must never see oracle answers or control the verifier. Report the complete denominator, failures, recovery, measured cost and latency, and exact deployed SHA. Record baseline and matched-model comparisons; no frontier-superiority claim without actual evidence.

A missing capability, absent probe, unverified trace, unknown cost, or failed safety gate cannot be silently reclassified as success. A scorer unit-test pass is not product qualification. Do not activate paid tests, public execution, production flags or deploy without the corresponding operator authorization and budgets.

## Work ordering

First integrate and prove the sandbox/artifact path; then authenticated MCP reads/write approval and Hatchet recovery, with unified spend/authorization and receipt integrity. Improve decision/model selection, context and delegation using the same held-out evaluation protocol. Keep Operly a governed workspace consumer; do not create a parallel intelligence runtime.
