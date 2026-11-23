"""Missing or malformed failure telemetry must not be treated as observed zero."""
import pytest
from agent_platform.personal_bridge import execution_receipt_report

@pytest.mark.parametrize("count", [None, -1, "3", False, True, 1.5, {}, []])
def test_invalid_failure_count_is_unverified(count):
    receipt = execution_receipt_report({"status": "incomplete", "failed_tool_count": count})
    assert receipt["failed_tool_count"] == 0
    assert receipt["failure_count_verified"] is False
    assert receipt["objective_verified"] is False

def test_missing_failure_count_is_unverified():
    receipt = execution_receipt_report({"status": "incomplete"})
    assert receipt["failed_tool_count"] == 0
    assert receipt["failure_count_verified"] is False

@pytest.mark.parametrize("count, displayed", [(0, 0), (3, 3), (100, 100), (101, 100)])
def test_valid_count(count, displayed):
    receipt = execution_receipt_report({"status": "incomplete", "failed_tool_count": count})
    assert receipt["failed_tool_count"] == displayed
    assert receipt["failure_count_verified"] is True

def test_validity_does_not_prove_objective_success():
    receipt = execution_receipt_report({"status": "completed", "failed_tool_count": 0})
    assert receipt["failure_count_verified"] is True
    assert receipt["objective_verified"] is False
