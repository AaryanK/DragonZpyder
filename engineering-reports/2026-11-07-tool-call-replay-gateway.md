# Hourly frontier engineering — tool-call replay and forced-tool validation

**Date:** 2026-11-07, America/Chicago. **Scope:** staging draft PR #33 only.

## Starting state
- Default branch: `master`; draft PR #33 targets `codex/consolidate-dragonzpyder-web` from `chore/lean-platform-cleanup-20261107`.
- Prior head `26a0a6f2b643c344dbe0724934a74ec5a7a4b18d`, with budget recovery improvements. No production merge.
- Railway staging: eight services, seven online and Personal Core sleeping; no recent deployment failures, warnings, critical issues or pending changes.
- Atomic USD reservations exist as an unwired primitive; paid parallel fan-out is still fail-closed. A gateway integration needs authenticated parent/job scope and durable per-request settlement.

## Selected bounded improvement

A protocol-history integrity gap in `api/agent_platform/gateway_protocol.py` allowed a previously completed assistant tool-call ID to be reused in a later turn. Duplicate IDs were only checked *within* one assistant message, so replayed identifiers could confuse downstream correlation and audit evidence. Also, a forced `tool_choice` function name was syntax-checked but not required to match the request's declared tool names; the gateway would forward an undeclared function choice to the provider.

Implemented:
1. Track IDs across the entire bounded message transcript, rejecting a later assistant turn that reuses a prior call ID.
2. Reject `tool_choice` when the request declares no tools, and reject forced function choices not in the validated declared tool list.
3. Preserve valid multi-turn conversations with distinct IDs and valid declared function choices.

Added regression cases in `api/tests/test_agent_gateway_protocol.py`: completed-turn replay rejected; fresh ID accepted; undeclared forced function rejected; declared function accepted; all choice modes without tools rejected.

Commits:
- `5cdfd3222d3d115f10706f523873ee455fe3d453`: protocol validation
- `bc208b398df765e6fdf079ac579e3dbe7702d10c`: tests

## Verification and evidence limits

GitHub CI run for `bc208b3`: https://github.com/AaryanK/DragonZpyder/actions/runs/42422973596 . CI status must be checked at the end of the cycle. No model inference was purchased, no external action was executed, and no actual frontier-model performance result is claimed. The tests exercise local protocol invariants, not adversarial provider behavior in live inference.

This change does not authorize executing tools; the gateway only transports tool-call requests. The agent-runtime credential remains separate from workspace/tenant capabilities. The new checks do not replace the gateway-side shared budget or trusted tool execution verification.

## Next highest-impact gate

Integrate an authenticated job/tenant-scoped reservation into the inference gateway **before** upstream dispatch. Require a fresh idempotency key and a server-validated budget lease for every paid child call; reconcile authoritative provider cost, retain unknown-cost holds, and block duplicate dispatch across retries/restarts. Exercise a fake provider with real PostgreSQL before enabling any paid fan-out. Then conduct one approved metered real-model tool-call smoke and independently judged long-horizon task, reporting actual success, false-success, latency and cost.
