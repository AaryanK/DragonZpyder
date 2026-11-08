"""No-credit, fail-closed checks of OpenRouter spending-cap preflight."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_platform.key_budget import evaluate_key_budget


def record(limit=0.5, remaining=0.5, reset=None):
    return {"data": {"limit": limit, "limit_remaining": remaining, "limit_reset": reset}}


def test_nonresetting_half_dollar_key_is_approved():
    assert evaluate_key_budget(record())["approved"] is True
    assert evaluate_key_budget(record(remaining=0.01))["approved"] is True


def test_soft_balance_or_missing_key_cap_cannot_authorize_paid_test():
    for payload in ({}, {"data": {}}, record(limit=None), record(limit=5), record(limit=0.51),
                    record(limit="NaN"), record(remaining=None), record(remaining=-1),
                    record(remaining=0), record(remaining=0.9), record(reset="daily"),
                    record(reset="monthly")):
        assert evaluate_key_budget(payload).get("approved") is not True


def test_rejects_string_injection_and_boolean_caps():
    assert evaluate_key_budget(record(limit=True)).get("approved") is not True
    assert evaluate_key_budget(record(limit="0.5; DELETE")).get("approved") is not True
