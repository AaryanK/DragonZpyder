"""Evaluation integrity characterization: zero-cost, non-deploying CI tests.

These tests deliberately demonstrate what heuristic smoke checks cannot prove.
Do not change them to assert that a smoke pass is an authenticated delivery.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_platform.evaluation import load_cases, score_case, summarize


def test_negated_delivery_claim_can_pass_heuristic_but_never_verification():
    """A substring match is not evidence of successful file delivery."""
    case = {
        "id": "negated-delivery",
        "required": ["created report"],
        "required_tools": ["write_file"],
    }
    result = score_case(
        case,
        "I created report, but did not save it and cannot deliver the file.",
        tool_names=["write_file"],
    )
    assert result["smoke_passed"] is True
    assert result["evaluation_class"] == "heuristic-smoke-only"
    assert result["verified_completion"] is False
    assert summarize([result])["verified_completions"] == 0


def test_tool_name_without_receipt_cannot_verify_completion():
    """Even a reported tool name and required text lack artifact provenance."""
    case = {
        "id": "untrusted-tool-name",
        "required": ["report complete"],
        "required_tools": ["write_file", "read_file"],
    }
    result = score_case(
        case,
        "report complete",
        tool_names=["write_file", "read_file"],
    )
    assert result["smoke_passed"] is True
    assert result["verified_completion"] is False


def test_current_baseline_has_no_external_delivery_oracle():
    """Pin current coverage as a warning, not as a success-rate benchmark."""
    cases = load_cases()
    requiring_tools = [c for c in cases if c.get("required_tools")]
    assert len(cases) == 12
    assert len(requiring_tools) == 1
    assert requiring_tools[0]["id"] == "virtual-workspace"
    assert all("receipt_oracle" not in c for c in cases)
