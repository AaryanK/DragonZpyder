"""Deterministic, synthetic acceptance probes for DragonZpyder agents.

These are *smoke checks*, not claims of frontier model quality or autonomous
task completion. Real benchmarks must additionally inspect artifacts and
external-world evidence, costs, time, and approvals.
"""
from __future__ import annotations

import json
from pathlib import Path


CASES_FILE = Path(__file__).with_name("evals") / "baseline.json"


def load_cases():
    document = json.loads(CASES_FILE.read_text(encoding="utf-8"))
    cases = document.get("cases")
    if document.get("version") != 1 or not isinstance(cases, list):
        raise ValueError("Invalid benchmark manifest")
    ids = set()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("Invalid benchmark case")
        ident = case.get("id")
        if not isinstance(ident, str) or ident in ids:
            raise ValueError("Duplicate or invalid benchmark ID")
        ids.add(ident)
        for key in ("required", "forbidden", "required_tools"):
            if key in case and (not isinstance(case[key], list)
                                or not all(isinstance(v, str) and v for v in case[key])):
                raise ValueError("Invalid benchmark rubric")
    return cases


def score_case(case: dict, answer: str, tool_names=()) -> dict:
    """Return transparent checks; no LLM judge or unverifiable success labels."""
    if not isinstance(answer, str):
        raise ValueError("Answer must be text")
    lower = answer.casefold()
    called = set(tool_names)
    missing_terms = [
        term for term in case.get("required", [])
        if term.casefold() not in lower
    ]
    disallowed = [
        term for term in case.get("forbidden", [])
        if term.casefold() in lower
    ]
    missing_tools = [
        name for name in case.get("required_tools", []) if name not in called
    ]
    return {
        "case_id": case["id"],
        "smoke_passed": not (missing_terms or disallowed or missing_tools),
        "missing_terms": missing_terms,
        "forbidden_claims": disallowed,
        "missing_tool_evidence": missing_tools,
        "evaluation_class": "heuristic-smoke-only",
    }


def summarize(scores: list[dict]):
    return {
        "suite": "synthetic-smoke",
        "passed": sum(bool(item["smoke_passed"]) for item in scores),
        "total": len(scores),
        "warning": "String/tool checks cannot establish accuracy or real task completion.",
    }
