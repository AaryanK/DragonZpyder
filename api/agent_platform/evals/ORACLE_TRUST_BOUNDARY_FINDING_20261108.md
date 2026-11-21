# Frontier stress oracle trust-boundary finding — 2026-11-08 UTC

## Scope and independently reproducible finding

Reviewed draft PR #33 head `93363cc4374a6f8b951c7189e998ccf4fb4ce417`, specifically `api/agent_platform/frontier_stress.py::score_report` and `api/tests/test_frontier_stress.py::test_agent_self_claim_cannot_replace_independent_outcome_oracle`.

**Finding: a caller-supplied dictionary is currently sufficient to satisfy the outcome-oracle component of the grader.** The condition is only `isinstance(oracle, dict) and oracle.get("case_id") == case["id"] and oracle.get("passed") is True`. No signature, verifier identity, trusted sandbox state, immutable run binding, or provenance is checked. The source itself warns that live infrastructure must authenticate the judge. The existing test deliberately demonstrates that `{"case_id": "F08", "passed": True}` can set `objective_verified=True` when all other evidence inputs are supplied.

This is **not** evidence of a compromised deployment. The current single-case live runner calls `score_report` without an oracle, so it cannot claim verified success through this path. It is a future integration hazard: any external endpoint that accepts untrusted `oracle`, `receipts`, `spans`, or `report` objects and passes them directly to the grader could fabricate a verified-success result.

## Checkable reproduction (offline, no model credits)

In `api/tests/test_frontier_stress.py`, `test_agent_self_claim_cannot_replace_independent_outcome_oracle` builds F08 report/artifact/readback/receipt/overlap evidence and verifies:
- Without an oracle: `objective_verified is False`.
- With wrong case ID: `objective_verified is False`.
- With a bare `{"case_id": "F08", "passed": True}`: `objective_verified is True`.

That last assertion proves the trust boundary is not enforced **inside the grader**. It does not prove an attacker controls the caller.

## Recommended reversible remediation

1. Distinguish `evidence_complete` from `verified_success`; never let a generic dictionary authorize the latter.
2. Require a trusted verifier service to issue a versioned, authenticated verdict bound to `run_id`, `case_id`, artifact content digests, tool transcript digest, environment snapshot ID, and expiration. Verify signature or a strictly private service-to-service identity before calling `score_report`.
3. Verify receipts and span provenance from the same run; reject caller-generated timestamps and duplicate agent identities.
4. Add negative tests for forged verdicts, wrong-run replay, changed artifact digests, expired verdicts, and missing sandbox execution. Preserve current no-oracle live-run fail-closed behavior.
5. Do not advertise frontier parity until independently verified end-to-end artifacts and matched real-model baselines exist.

## Operational observations

Railway project `DRAGONZPYDER AGENT STAGING`, environment `staging`: no pending staged patch. Gateway, Hatchet Worker, Agent Test Lab, three PostgreSQL services and Hatchet report latest deployment SUCCESS; Personal Core reports SLEEPING. Gateway/Worker/Lab are sourced from `chore/lean-platform-cleanup-20261107`. This deployment status does not establish endpoint-level or agent-task health.

No paid inference, production change, merge, or external publication was initiated by this review. No CI tests were executed in this review; source-level test behavior was inspected rather than re-run.
