"""Fail-closed integrity checks for durable monitor receipts (no database required)."""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_platform.local_monitor import _format


BUCKET = datetime(2026, 11, 19, 8, 0, tzinfo=timezone.utc)
OBSERVATION = {"memory": {"used_percent": 91.0}, "disk": {"used_percent": 50.0}}
DECISION = {"status": "attention", "alerts": ["ram_high"]}


def receipt(observation=OBSERVATION, decision=DECISION):
    payload = {
        "monitor_key": "worker-health",
        "bucket_start": BUCKET.isoformat(),
        "observation": observation,
        "decision": decision,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


@pytest.mark.parametrize("inserted", [False, True])
@pytest.mark.parametrize("as_json", [False, True])
def test_valid_receipt_accepts_both_paths_and_json_representations(inserted, as_json):
    row = {
        "observation": json.dumps(OBSERVATION) if as_json else OBSERVATION,
        "decision": json.dumps(DECISION) if as_json else DECISION,
        "receipt_sha256": receipt(),
    }
    result = _format("worker-health", BUCKET, row, inserted=inserted)
    assert result["status"] == "attention"
    assert result["new_observation"] is inserted


@pytest.mark.parametrize("field,value", [
    ("decision", {"status": "healthy", "alerts": []}),
    ("observation", {"memory": {"used_percent": 10.0}, "disk": {"used_percent": 50.0}}),
    ("receipt_sha256", "0" * 64),
])
def test_modified_receipt_fails_closed(field, value):
    row = {"observation": OBSERVATION, "decision": DECISION, "receipt_sha256": receipt()}
    row[field] = value
    with pytest.raises(RuntimeError, match="receipt integrity mismatch"):
        _format("worker-health", BUCKET, row, inserted=False)


def test_receipt_bound_to_monitor_identity_and_bucket():
    row = {"observation": OBSERVATION, "decision": DECISION, "receipt_sha256": receipt()}
    with pytest.raises(RuntimeError, match="receipt integrity mismatch"):
        _format("other-monitor", BUCKET, row, inserted=False)
    with pytest.raises(RuntimeError, match="receipt integrity mismatch"):
        _format("worker-health", BUCKET.replace(minute=5), row, inserted=False)
