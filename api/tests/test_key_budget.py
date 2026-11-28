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



def test_production_parent_key_ceiling_is_separate_from_staging(monkeypatch):
    from agent_platform.key_budget import parent_key_ceiling
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "production")
    ceiling = parent_key_ceiling()
    assert evaluate_key_budget(record(limit=3, remaining=1), max_total=ceiling)["approved"] is True
    for payload in (record(limit=3.01, remaining=1), record(limit=3, remaining=0),
                    record(limit=3, remaining=1, reset="daily"), record(limit=None)):
        assert evaluate_key_budget(payload, max_total=ceiling)["approved"] is False
    # Default staging callers stay restricted even in a production process.
    assert evaluate_key_budget(record(limit=3, remaining=1))["approved"] is False
    for environment in ("staging", "unknown", ""):
        monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", environment)
        assert evaluate_key_budget(record(limit=3, remaining=1),
                                   max_total=parent_key_ceiling())["approved"] is False
