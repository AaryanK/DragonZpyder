"""Fixed offline Operly business-broker contract smoke, Railway cron friendly.

Runs exactly the checked-in synthetic HTTP broker tests with no model,
real accounts, network broker, paid inference or business writes.
This is not a production workflow or a live Operly smoke.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

_ALLOWED_KEYS = (
    "DRAGONZPYDER_OPERLY_BROKER_TOKEN",
    "DRAGONZPYDER_OPERLY_CANARY_LEASE",
    "OPENROUTER_API_KEY",
    "HATCHET_CLIENT_TOKEN",
)


def execute() -> int:
    now = datetime.now(timezone.utc).isoformat()
    if (os.getenv("DRAGONZPYDER_STAGE") != "staging"
            or os.getenv("DRAGONZPYDER_SYNTHETIC_BUSINESS_CANARY_ENABLED") != "1"):
        print(json.dumps({"event": "dz_business_synthetic_canary", "status": "disabled",
                          "timestamp_utc": now}), flush=True)
        return 2

    # Keep this isolated test service credential-free. The checked-in test
    # fixtures mock the Operly transport with httpx.MockTransport.
    if any(os.getenv(key) for key in _ALLOWED_KEYS):
        print(json.dumps({"event": "dz_business_synthetic_canary",
                          "status": "unexpected_credentials", "timestamp_utc": now}), flush=True)
        return 3

    root = Path(__file__).resolve().parents[1]
    test = root / "tests" / "test_operly_business_canary.py"
    if not test.is_file():
        print(json.dumps({"event": "dz_business_synthetic_canary", "status": "test_missing",
                          "timestamp_utc": now}), flush=True)
        return 4

    try:
        # Fixed command, no user-controlled shell or arbitrary test selection.
        # Run output includes only intentionally synthetic fixtures.
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "--disable-warnings",
             str(test)],
            cwd=str(root), capture_output=True, text=True,
            timeout=90, check=False,
            env={
                "PATH": os.getenv("PATH", ""),
                "HOME": os.getenv("HOME", "/tmp"),
                "PYTHONPATH": str(root),
                "DRAGONZPYDER_STAGE": "staging",
            },
        )
    except subprocess.TimeoutExpired:
        print(json.dumps({"event": "dz_business_synthetic_canary",
                          "status": "timeout", "timestamp_utc": now}), flush=True)
        return 5

    # Don't persist tool outputs/customer fixtures, secrets or raw test trace.
    print(json.dumps({
        "event": "dz_business_synthetic_canary",
        "status": "passed" if result.returncode == 0 else "failed",
        "timestamp_utc": now,
        "exit_code": result.returncode,
        "suite": "tests/test_operly_business_canary.py",
        "execution": "synthetic_broker_contract_only",
        "external_mutations": 0,
        "paid_model_calls": 0,
    }, sort_keys=True), flush=True)
    return result.returncode


def main() -> None:
    sys.exit(execute())


if __name__ == "__main__":
    main()
