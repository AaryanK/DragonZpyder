# DragonZpyder Hourly Frontier Engineering — first on-demand run

**Date:** 2026-11-07 UTC. **Change scope:** draft staging PR #33,
`chore/lean-platform-cleanup-20261107`. No production merge, paid inference,
external account changes, permissions broadening, or destructive cleanup.

## Starting state

- PR #33 head `e549600d44bb8b9584e239c36434bca507e78a2a`,
  draft/open, four API workflow jobs green from the previous cycle.
- Railway staging health: eight services, zero warnings/failures,
  no pending deployments at the start of this run. A successful
  deployment does not imply live agent task success.
- Known frontier weaknesses: no independently verified real-model
  long-horizon completion, no general isolated sandbox, no atomic
  multi-child total-USD budget, and earlier model tool-call/502 failures.
- The evaluator previously accepted requested checkpoint paths plus
  unrelated successful `write_file`/`read_file` tool calls as sufficient
  artifact evidence if a separate oracle were supplied. This is an
  evidence-integrity weakness and can over-credit unrelated work.

## Selected improvement: correlate each artifact to its own tool evidence

Implemented:
- `api/agent_platform/artifact_evidence.py`: bounded extraction of
  LangChain `AIMessage.tool_calls` and matching successful
  `ToolMessage` replies; links exact `/workspace/...` path and
  tool-call ID; requires a successful write, then a later-turn read,
  and final checkpoint state at the same exact path.
- Later successful edits invalidate earlier readbacks; errors,
  mismatched IDs, duplicate/replayed IDs, path escapes and same-turn
  concurrent write/read cannot earn evidence.
- `runtime.py` now returns `artifact_readback_paths` as structured,
  sanitized, path-specific evidence, without logging tool content.
- `frontier_stress.py` requires path-specific readback of **every**
  expected artifact; generic read tool activity is no longer
  sufficient. The evaluator now reports `artifact_files_read_back`.
- Added `tests/test_artifact_evidence.py` (adversarial edge cases),
  upgraded `tests/test_frontier_stress.py` (wrong-file and missing
  receipt cannot score a pass), and added a **real LangGraph offline
  write-then-read tool loop** to `tests/test_harness_v2.py`.
- CI workflow explicitly runs the new artifact evidence tests.

**Evidence boundary:** This verifies tool dispatch and readback events
for virtual files, not the correctness of file contents or the
trustworthiness of a supplied external oracle. It does not certify
a task complete and is not proof of frontier-agent parity.

## GitHub evidence

- Implementation commits:
  - `27c5758dd67062e32ccc4271bc66739573a7a697`
  - `e2e8838713297732a5d681f259fb192ab8d13c90`
  - `ffce65e8179d2d1450c3e97b15237119d5358547`
- Adversarial and integration test commits:
  - `4febbab0838e312ac80888022d3bc800b5eb3a62`
  - `81ca41c873485abc1da7b957f09db732a308e076`
  - `7f5ae907c79e911699f2a4ecb528fc5be23ddfc7`
  - `489c474af194e99852af4bfed3e15682474a8b64`
  - `e3e9660dcc7a4fe0e3893a984240dbf39f19202c`
- All GitHub workflows **passed** at head
  `e3e9660dcc7a4fe0e3893a984240dbf39f19202c`.
  API workflow: https://github.com/AaryanK/DragonZpyder/actions/runs/42395723130
  - `agent-stack-imports`: **96 passed, 1 LangChain QuickJS beta warning**
  - `fastapi-contract`: **35 passed, 1 Starlette/httpx deprecation warning**
  - Personal Core and legacy compatibility jobs passed.
  - Web and general CI workflow checks passed.

## Real-world benchmark status

- The ten hard stress prompts remain original, requiring multiple
  independent subtracks and verifiable sandbox/environment outcomes.
- **New real model trials performed this cycle: 0.**
- **Independently verified frontier task completions this cycle: 0.**
- No frontier parity result can be inferred from the 131 passing
  offline contracts. Staging Gateway and Agent Lab deployments were
  only checked for service health, not end-to-end task completion.
- No obsolete production code deleted: absence of a dependency/traffic
  proof is not a reason to remove a rollback surface.

## Next highest-impact engineering gate

Create an **atomic cross-child spend/reservation budget** (DB-backed)
before enabling paid concurrent model evaluation. Tie each delegated
model request to its job/tenant budget and enforce server-side
reservation and release, including partial failures/restarts.
Only then perform a single bounded real-model tool-call smoke and
an independently checked F08 artifact task, followed by measured
multi-run, multi-model frontier comparisons. Track correctness,
latency, USD and false-success rate rather than appearance or length.
