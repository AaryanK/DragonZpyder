"""Operator-invoked, small and cost-bounded *diagnostic* eval runner.

Never called by CI or boot hooks; explicitly opt in before spending credits.
Only synthetic prompts from the checked-in test manifest are accepted.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from uuid import uuid4

from .evaluation import load_cases, score_case, summarize
from .runtime import AgentRuntime


def evaluation_enabled():
    return (
        os.getenv("DRAGONZPYDER_AGENT_EVAL_ALLOW_PAID") == "1"
        and os.getenv("DRAGONZPYDER_AGENT_USE_GATEWAY") == "1"
        and os.getenv("DRAGONZPYDER_AGENT_PRODUCTION_MODE") == "1"
        and os.getenv("DRAGONZPYDER_AGENT_HARNESS_V2") == "1"
    )


async def evaluate(case_ids: list[str]) -> dict:
    if not evaluation_enabled():
        raise RuntimeError("Paid agent evaluations require explicit gateway-only opt-in")
    if not 1 <= len(case_ids) <= 2 or len(set(case_ids)) != len(case_ids):
        raise ValueError("Select one or two distinct cases maximum")
    available = {c["id"]: c for c in load_cases()}
    if any(cid not in available for cid in case_ids):
        raise ValueError("Unknown synthetic evaluation case")
    scores = []
    runtime = AgentRuntime()
    await runtime.start()
    try:
        for cid in case_ids:
            case = available[cid]
            started = time.monotonic()
            try:
                report = await asyncio.wait_for(runtime.run_report(
                    service_id="agent-smoke",
                    thread_id="eval-" + uuid4().hex[:20],
                    prompt=case["objective"],
                ), timeout=180)
                score = score_case(
                    case, report["answer"],
                    tool_names=report["successful_tools"],
                )
                score["virtual_artifact_count"] = len(report["virtual_artifact_paths"])
                score["failed_tool_count"] = report["failed_tool_count"]
            except Exception as exc:
                # Never log model prompts, tokens, credentials, exception text or
                # raw tool arguments from evaluation failures.
                score = {
                    "case_id": cid, "smoke_passed": False,
                    "failure_type": type(exc).__name__,
                    "evaluation_class": "heuristic-smoke-only",
                }
            score["duration_s"] = round(time.monotonic() - started, 2)
            scores.append(score)
    finally:
        await runtime.close()
    return {"summary": summarize(scores), "case_results": scores}


def main():
    import sys
    ids = sys.argv[1:]
    result = asyncio.run(evaluate(ids))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
