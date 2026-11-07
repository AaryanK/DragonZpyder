"""Strict outcome-first evaluator for the 10 DragonZpyder long-horizon cases.

No model call occurs from this module without explicit, one-case opt-in.
Outputs are evidence-based *readiness* or partial diagnostics, never automatic
frontier-parity claims. This is NOT a synthetic scoring leaderboard.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from time import monotonic
from uuid import uuid4

SUITE = Path(__file__).with_name("evals") / "frontier_stress_v1.json"

# Capabilities verified wired into the V2 *agent*, not present elsewhere in Railway.
CAPABILITIES = frozenset({"filesystem", "web_search", "inline_subagents"})
EXTERNAL_RECEIPT_KINDS = frozenset({
    "sandbox_test", "browser_state", "authorized_portal", "live_source",
    "scheduled_run", "published_artifact",
})


def load_suite() -> list[dict]:
    manifest = json.loads(SUITE.read_text(encoding="utf-8"))
    if manifest.get("version") != 1 or manifest.get("kind") != "long_horizon_stress_eval":
        raise ValueError("Unknown frontier stress suite version")
    cases = manifest.get("cases")
    if not isinstance(cases, list) or len(cases) != 10:
        raise ValueError("Exactly ten test cases required")
    identities, domains = set(), set()
    for case in cases:
        case_id = case.get("id")
        if not isinstance(case_id, str) or case_id in identities:
            raise ValueError("Duplicate or invalid case ID")
        identities.add(case_id)
        domain = case.get("domain")
        if domain in domains:
            raise ValueError("Stress domains must be distinct")
        domains.add(domain)
        prompt = case.get("prompt")
        if not isinstance(prompt, str) or len(prompt.split()) < 450 or len(prompt) > 12000:
            raise ValueError("Each stress prompt must be 450+ words and fit model request contract")
        tracks = case.get("tracks", [])
        artifacts = case.get("expected_artifacts", [])
        capabilities = case.get("required_capabilities", [])
        if not isinstance(tracks, list) or len(tracks) < 3:
            raise ValueError("Require independent subtracks")
        if not isinstance(artifacts, list) or len(artifacts) < 3 or not all(
            isinstance(p, str) and p.startswith("/") is False
            and ".." not in p and "/" not in p for p in artifacts
        ):
            raise ValueError("Case must name three safe relative artifact files")
        if not isinstance(capabilities, list) or not capabilities:
            raise ValueError("Missing declared capability contracts")
        artifact_dir = case.get("artifact_dir")
        if not isinstance(artifact_dir, str) or not re.fullmatch(
            r"/workspace/[a-zA-Z0-9_-]+", artifact_dir
        ):
            raise ValueError("Missing or unsafe exact artifact directory")
        if any(f"{artifact_dir}/{name}" not in prompt for name in artifacts):
            raise ValueError("Prompt must specify each artifact's exact path")
    return cases


def parallel_overlap(spans: list[dict] | None) -> bool:
    """Parallelism requires measured overlapping time intervals, not claims."""
    if not isinstance(spans, list):
        return False
    valid = []
    for span in spans:
        if not isinstance(span, dict):
            continue
        name, start, end = span.get("agent"), span.get("start_ms"), span.get("end_ms")
        if (not isinstance(name, str) or not name or
                type(start) not in (int, float) or type(end) not in (int, float)
                or end <= start):
            continue
        valid.append((name, start, end))
    return any(
        a[0] != b[0] and max(a[1], b[1]) < min(a[2], b[2])
        for i, a in enumerate(valid) for b in valid[i + 1:]
    )


def score_report(case: dict, report: dict | None, *,
                 supported: set[str] | frozenset[str] = CAPABILITIES,
                 receipts: list[dict] | None = None,
                 spans: list[dict] | None = None,
                 oracle: dict | None = None) -> dict:
    missing_capabilities = sorted(set(case["required_capabilities"]) - set(supported))
    if not report:
        return {
            "id": case["id"], "status": "not_executed",
            "missing_capabilities": missing_capabilities, "objective_verified": False,
        }
    state_paths = set(report.get("virtual_artifact_paths") or [])
    # Never credit an artifact from a model's statement alone: it must be
    # present in checkpoint state and accompanied by a real writing tool.
    artifacts = case["expected_artifacts"]
    # A same-named file in the wrong workspace is NOT the requested artifact.
    artifact_dir = case["artifact_dir"]
    present = {
        name for name in artifacts if f"{artifact_dir}/{name}" in state_paths
    }
    actual_tools = set(report.get("successful_tools") or [])
    written = "write_file" in actual_tools or "edit_file" in actual_tools
    read_back = "read_file" in actual_tools
    receipts = receipts if isinstance(receipts, list) else []
    proved_kinds = sorted({
        r["kind"] for r in receipts if isinstance(r, dict)
        and r.get("verified") is True and r.get("kind") in EXTERNAL_RECEIPT_KINDS
    })
    parallel = parallel_overlap(spans)
    has_artifacts = written and read_back and len(present) == len(artifacts)
    has_oracle = bool(proved_kinds) and not missing_capabilities
    # Source and artifact checks are necessary but not sufficient: a native
    # sandbox/environment-state judge must attest complete objective success.
    # Agent self-reporting cannot certify its own success. The caller must
    # supply a separate trusted outcome judge's verdict, keyed to this case.
    # An arbitrary caller-provided "passed" flag is not itself a signed
    # certificate; live infrastructure must authenticate the judge.
    oracle_ok = bool(
        isinstance(oracle, dict) and oracle.get("case_id") == case["id"]
        and oracle.get("passed") is True
    )
    outcome_proven = bool(
        oracle_ok and has_artifacts and has_oracle and parallel
        and not missing_capabilities
    )
    return {
        "id": case["id"],
        "status": (
            "verified_success" if outcome_proven else
            "capability_blocked" if missing_capabilities else
            "insufficient_evidence"
        ),
        "objective_verified": outcome_proven,
        "artifact_files_created": sorted(present) if written else [],
        "artifact_files_required": artifacts,
        "read_back_observed": read_back,
        "parallelism_observed": parallel,
        "independent_outcome_oracle_passed": oracle_ok,
        "external_receipt_kinds": proved_kinds,
        "missing_capabilities": missing_capabilities,
        "model_run_success_claim": bool(report.get("objective_verified")),
        "warning": "No file content or external result is credited without independent checks.",
    }


def readiness_report() -> dict:
    suite = load_suite()
    return {
        "suite": "frontier_stress_v1",
        "kind": "capability_readiness_only_not_model_benchmark",
        "cases": [score_report(case, None) for case in suite],
        "count": len(suite),
        "distinct_domains": len({c["domain"] for c in suite}),
        "prompt_word_counts": {c["id"]: len(c["prompt"].split()) for c in suite},
        "real_model_runs": 0,
        "all_cases_outcome_verified": False,
    }


def live_eval_enabled() -> bool:
    return all(os.getenv(key) == "1" for key in (
        "DRAGONZPYDER_AGENT_EVAL_ALLOW_PAID",
        "DRAGONZPYDER_AGENT_USE_GATEWAY",
        "DRAGONZPYDER_AGENT_PRODUCTION_MODE",
        "DRAGONZPYDER_AGENT_HARNESS_V2",
        "DRAGONZPYDER_AGENT_STRESS_EVAL_ENABLED",
    ))


async def run_live_case(case_id: str) -> dict:
    """Operator-triggered ONE-case diagnostic, never automated by CI or boot."""
    if not live_eval_enabled():
        raise RuntimeError("Paid stress model evaluation is disabled")
    suite = {c["id"]: c for c in load_suite()}
    if case_id not in suite:
        raise ValueError("Unknown long-horizon case")
    from .runtime import AgentRuntime
    case = suite[case_id]
    started = monotonic()
    runtime = AgentRuntime()
    await runtime.start()
    try:
        try:
            # Most cases deliberately require capabilities the agent lacks.
            # Executing them can still measure *honesty* and partial progress.
            report = await asyncio.wait_for(runtime.run_report(
                service_id="frontier-stress",
                thread_id="f10-" + uuid4().hex[:20],
                prompt=case["prompt"],
            ), timeout=240)
            score = score_report(case, report)
            # Do not emit private model outputs or prompt text into logs.
            score["successful_tool_count"] = len(report["successful_tools"])
            score["failed_tool_count"] = report["failed_tool_count"]
        except Exception as exc:
            # Safe diagnostic classes and HTTP status only. Never retain
            # raw exception messages, prompts, tool arguments or secrets.
            cause = exc.__cause__ or exc
            http_status = getattr(cause, "status_code", None)
            score = {
                "id": case_id, "status": "execution_failed",
                "exception_type": type(cause).__name__,
                "error_phase": getattr(exc, "phase", "unknown"),
                "http_status": http_status if type(http_status) is int else None,
                "objective_verified": False,
            }
    finally:
        await runtime.close()
    score["elapsed_s"] = round(monotonic() - started, 2)
    score["comparison_with_frontier_labs"] = "not_available"
    return score


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--live-case", choices=[c["id"] for c in load_suite()])
    args = parser.parse_args()
    if args.live_case:
        print(json.dumps(asyncio.run(run_live_case(args.live_case)), sort_keys=True))
    else:
        print(json.dumps(readiness_report(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
