"""Fail-closed, provider-enforced per-key cap preflight for paid staging tests.

This does not infer a spending ceiling from the key balance or an account's
available credits. Only a verified, non-resetting OpenRouter key limit at or
below the approved total can authorize a staged paid test.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import httpx

MAX_STAGING_TOTAL_USD = Decimal("0.50")


def _dollar(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return amount if amount.is_finite() and amount >= 0 else None


def evaluate_key_budget(payload: object) -> dict:
    """Treat missing, resettable or larger key caps as NOT approved."""
    def denied(reason: str) -> dict:
        return {"approved": False, "reason": reason}

    if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
        return denied("invalid_provider_budget_response")
    data = payload["data"]
    cap = _dollar(data.get("limit"))
    remaining = _dollar(data.get("limit_remaining"))
    if cap is None or cap <= 0:
        return denied("key_has_no_verified_hard_cap")
    if cap > MAX_STAGING_TOTAL_USD:
        return denied("key_hard_cap_exceeds_approved_total")
    # A resetting key could incur more than $0.50 across separate windows.
    if data.get("limit_reset") is not None:
        return denied("resettable_key_cap_not_permitted")
    if remaining is None or remaining > cap:
        return denied("invalid_remaining_budget")
    if remaining <= 0:
        return denied("key_budget_exhausted")
    return {
        "approved": True,
        "reason": "hard_nonresetting_key_cap_verified",
        "limit_usd": str(cap),
        "remaining_usd": str(remaining),
    }


async def verify_key_budget(client: httpx.AsyncClient, key: str) -> dict:
    if not isinstance(key, str) or len(key) < 20:
        return {"approved": False, "reason": "provider_key_unavailable"}
    try:
        response = await client.get(
            "https://openrouter.ai/api/v1/key",
            headers={"Authorization": "Bearer " + key},
            timeout=9,
        )
        if response.status_code != 200:
            return {"approved": False, "reason": "provider_budget_lookup_failed"}
        return evaluate_key_budget(response.json())
    except (httpx.HTTPError, ValueError, TypeError):
        return {"approved": False, "reason": "provider_budget_lookup_failed"}
