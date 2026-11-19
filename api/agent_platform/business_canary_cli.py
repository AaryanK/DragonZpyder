"""Operator-only staging test entrypoint; NEVER supply leases as CLI arguments.

A valid, fresh Operly-issued user-scoped delegation is required for actual
business reads. No credential or business payload is printed or persisted.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os

from .business_canary import BusinessCanaryError, run_business_canary


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only Operly business canary")
    parser.add_argument("template", choices=("daily_operations", "business_search", "customer_review"))
    parser.add_argument("--query", default=None)
    parser.add_argument("--contact-id", default=None)
    args = parser.parse_args()
    lease = os.getenv("DRAGONZPYDER_OPERLY_CANARY_LEASE", "")
    if not 20 <= len(lease) <= 6000:
        raise BusinessCanaryError("Fresh Operly-issued staging delegation is required")
    outcome = asyncio.run(run_business_canary(
        lease=lease, template=args.template,
        query=args.query, contact_id=args.contact_id,
    ))
    # No raw business data, identity, token, provider trace, or prompt output.
    print(json.dumps(outcome, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
