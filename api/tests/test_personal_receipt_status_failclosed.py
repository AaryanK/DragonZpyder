"""Fail-closed status classification for user-visible execution receipts."""
import pytest
from agent_platform.personal_bridge import execution_receipt_report


@pytest.mark.parametrize("status", [None, "", "failed", "paused", "cancelled", "running", 0, False, "COMPLETED", "incomplete"])
def test_noncompleted_status_never_claims_completion(status):
    report = execution_receipt_report({"status": status, "successful_tools": []})
    assert report["status"] == "incomplete"
    assert report["objective_verified"] is False


def test_missing_status_never_claims_completion():
    assert execution_receipt_report({})["status"] == "incomplete"


def test_exact_completed_status_is_preserved():
    assert execution_receipt_report({"status": "completed"})["status"] == "completed"
