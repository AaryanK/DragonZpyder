# DragonZpyder Frontier Engineering — scheduled iteration, 2026-11-07

## Starting state and environment
- Repository: `AaryanK/DragonZpyder`; default `master`; draft PR #33 targets `codex/consolidate-dragonzpyder-web`.
- PR head at start: `2435225f2c167d04da1f621ceab547209bd4bbb6`; all three GitHub workflow families passed.
- Railway staging environment: 8 services, 0 active warnings/critical alerts, 0 recent failed deployments and 0 pending deployments. Personal Core is sleeping, which is not a service failure.
- Prior cycle added path-correlated virtual artifact readback verification; do not repeat.
- Largest known frontier blocker remains lack of verified end-to-end real-model success and atomic total spend reservations across parallel children. Neither is solved by this patch.

## Finding and implementation
The agent startup preflight already examined `DRAGONZPYDER_AGENT_BUILDER_MODEL_ID`, but the actual `build_agent` constructor only passed analyst/verifier/researcher overrides to `specialist_models`. The builder therefore silently inherited the supervisor model even when an operator had selected an approved builder-specific model. This can invalidate per-role model comparisons, cost forecasts and capability selection.

**Change:** Include `builder` in the model-override loop in `api/agent_platform/runtime.py`. The existing `model_client` enforces the exact model allowlist, authenticated gateway and token limits; no new provider or permissions are enabled. `specialist_specs` already accepts the builder key. This is a narrow reversible fix, not a model performance improvement by itself.

**Regression tests:** Added two tests in `api/tests/test_harness_v2.py`: one captures the actual builder model handed to `build_frontier_agent` using a no-network model stub; the other proves an unapproved builder model fails closed under gateway mode.

## Commits and verification
- `3e9aca4ab2a5654028ee742d8100ef709f9cf2c5`: implement builder routing.
- `fd058a72f84e5b7f52389fe2bf531aebeb5f21ed`: add routing/allowlist regression tests.
- GitHub Actions API run: https://github.com/AaryanK/DragonZpyder/actions/runs/42398746372
- The tests are wired into the existing `agent-stack-imports` job. Final CI outcome should be checked against the latest PR head; queued/in-progress checks must not be described as passed.
- No paid inference, production deployment, merges, model trials or external writes occurred.

## Frontier gap and next action
The test fixes a silent per-specialist model-selection mismatch. Real model-tool success, correct external tool effects, robust multiagent budget accounting and apples-to-apples frontier parity remain **unverified**. The highest priority is a gateway-enforced atomic shared job budget (not just per-child model call limits), followed by a single explicitly approved, low-cost, independently checked model-tool smoke. Preserve operator approvals and fail-closed execution until that budget is enforceable.
