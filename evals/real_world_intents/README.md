# Real-world intent acceptance specifications

`cases.json` is the source of truth for 50 personal cases; `CASES.md` is its readable view. No case has been executed. Fixture descriptions are specifications, not implemented fixture files. Baseline `score: null` means unknown, not zero.

Use the existing Operly Personal runtime first through a narrow authenticated adapter; do not build a second planner or policy engine merely to run these cases. Full design and scoring rules: [architecture charter](https://github.com/AaryanK/Operly/blob/codex/two-product-architecture-benchmarks/docs/architecture/dragonzpyder-operly-2026-09-15.md).

A runner must provision isolated fixtures, drive the actual entrypoint, check effects through an independent oracle, inject approval/restart/provider-failure variants, and record usage/evidence. Fake-provider and scripted-model runs must be labelled separately from live-model and test-account acceptance. Targets are aspirations and never baseline claims.

All budgets apply cumulatively to active work across retries/resumes; wait time has its own deadline. Budget exhaustion yields a visible incomplete result. Score 6 requires verified completion and an appropriate permitted outcome/follow-up record, not an automatic permanent memory entry for every request.
