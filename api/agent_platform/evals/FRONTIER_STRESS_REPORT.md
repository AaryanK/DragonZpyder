# DragonZpyder Frontier-Style Stress Evaluation v1

**Status (2026-11-07):** 10 original long-horizon cases committed; dry-run
CI checks prompt compatibility and refuses unproven success. This suite is
**not** a published frontier benchmark, and no Codex/Claude run has been
performed on these exact 10 cases.

## Test philosophy

Inspired by public methodology from:
- OSWorld 2.0 (long-horizon and changing environments): https://arxiv.org/abs/2606.29537
- WeaveBench (hybrid GUI and code work): https://weavebench.github.io/
- WildClawBench (runtime-native agent tasks): https://arxiv.org/abs/2605.10912
- LangChain unified evals (autonomous, multi-turn, retrieval, research):
  https://github.com/langchain-ai/deepagents/blob/main/libs/evals/UNIFIED_EVALS.md

These tasks are **original**, not copied from a benchmark. A high score must
require actual tool actions and independently checked environment state, not
long, plausible-looking answers. Hold out test fixtures to reduce overfitting.

## The ten cases

| ID | Unrelated domain | Main outcomes | Required orchestration |
| --- | --- | --- | --- |
| F01 | Distributed checkout debugging | Crash-safe idempotent patch, tests, incident notes | App logic / DB / reliability subtracks |
| F02 | Scientific numerical computing | Magnetic map transform and falsification tests | Physics / interpolation / numeric review |
| F03 | Public-health evidence | Dated guideline synthesis and conflicts | Official guidance / studies / engineering |
| F04 | Accounting reconciliation | Book-to-bank reconciliation and exception ledger | Arithmetic / accruals / duplicates |
| F05 | Cultural archival research | Provenance catalog and cautious claims audit | Historical / linguistic / ownership |
| F06 | International travel logistics | Visa/itinerary risk matrix (no bookings) | Official rules / accessibility / cost |
| F07 | Security permissions | Tenant-scoped remediation, synthetic tests | IAM / replay defense / auditability |
| F08 | Adult education design | Full adaptive curriculum and diagnostic | Math / pedagogy / accessibility |
| F09 | Infrastructure incident response | Outage runbook and idempotent recovery | DB / queues / SLOs |
| F10 | Five-day Nepal watch | Monitoring state machine, portal drafts, expiry | Sources / scheduling / authorization |

Every prompt contains 450+ words, three separable tracks, conflicting
material and a requirement for at least three concrete virtual artifacts.
The 10 prompts total more than 5,000 words; none includes real private
records or authorization to affect external accounts.

## Current execution reality

Currently connected to V2:
- LangGraph / Deep Agents planning and checkpointing
- virtual /workspace/ read/write/edit/glob/grep
- inline researcher/analyst/verifier subagents (not proven background parallel)
- basic source snippet search (Wikipedia live-tested; wider source provider
  adapters need credentials/hosting)

**Missing for full completion:** general full-page fetch, trusted browser,
isolated sandbox execute, persistent user-owned cron, external application
publication and some outcome judges. Passing a ten-prompt *syntax check* must
never be described as matching frontier labs.

## Reproduce without model credits

From the `api/` directory:
```bash
python -m agent_platform.frontier_stress
pytest -q tests/test_frontier_stress.py
```

The Python module validates task diversity and returns the exact missing
capabilities per case; CI sends all 10 prompts through the real LangGraph
graph using a scripted fake model to confirm wiring and input handling. CI
makes **zero** hosted model calls.

## Controlled actual-model run

```bash
# Only in the trusted staging environment after checking operator budget.
# Requires gateway credentials and all other feature flags documented below.
DRAGONZPYDER_AGENT_STRESS_EVAL_ENABLED=1 \
DRAGONZPYDER_AGENT_EVAL_ALLOW_PAID=1 \
python -m agent_platform.frontier_stress --live-case F08
```

Required additionally:
- `DRAGONZPYDER_AGENT_USE_GATEWAY=1`
- `DRAGONZPYDER_AGENT_PRODUCTION_MODE=1`
- `DRAGONZPYDER_AGENT_HARNESS_V2=1`
- Existing authenticated staging model gateway and PostgreSQL checkpoints.

The CLI accepts **only one** case per invocation. The existing harness
limits eight supervisor model calls, three delegated task calls, three
model calls per specialist and 768 output tokens per call; it is
intentionally too small for many long tasks. The response supplies sanitized
tool evidence, not private model text. A separate staging-only,
database-deduplicated `F08` canary can run once when the operator enables
`DRAGONZPYDER_STAGING_FRONTIER_CANARY_ONCE=1` and both eval flags.
No recurring evaluation is created.

Do not increase stress-model-call limits or run all ten paid cases without
an operator-approved spend cap, model routing and experiment ID. A gateway
allowlist and request limits are necessary but not sufficient for a
global USD budget.

## Outcome grading contract

- Structural: ten prompt validity and diverse domains.
- Tool use: actual `write_file` and `read_file` tool messages plus matching
  checkpointed artifact paths, not the model's final claims.
- External: authenticated, separately verified sandbox/portal/source
  receipts and objective-specific outcome judges.
- Parallel: separate agent IDs with **overlapping measured start/end times**.
  Inline sequential subagents do not count as proven parallelism.
- Reliability: retries, interruption/restart, cancellation, deadline, and
  duplicate side-effect checks.
- Cost/latency: model and tool calls, metered USD costs, p50/p95 latency,
  total time and cost per *verified successful* task.
- Comparability: identical tasks, data, tool budgets, and scoring logic;
  at least three independent runs; both no-delegation and multiagent
  baselines; clean test environments and adversarial holdouts.

## Proposed promotion gates

1. All ten cases are valid and compile/invoke through the real graph without
   model credits (CI gate).
2. At least two real-model canaries complete with accurate honest artifact
   reports. Identify limits before raising budgets.
3. Run ten tasks against DragonZpyder with genuine sources, sandboxes and
   external-state judges; failures remain failures.
4. Measure parallel advantage against sequential delegation with timestamped
   traces, not just subagent count.
5. Run identical tasks with approved frontier models, and separately with
   their native harnesses if licensed and authorized. Publish per-case
   outcome, interventions, cost and limitations; **no parity claim**
   until comparable trials are completed.

**Never treat a mocked environment result as evidence that a real-world
action succeeded.**
