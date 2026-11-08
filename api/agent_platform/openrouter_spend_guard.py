"""Strict OpenRouter per-key cap verification for operator-only paid staging tests.

This check never creates credit or changes provider limits. A missing, reset,
unparseable or larger-than-approved limit fails closed before model dispatch.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

import httpx

KEY_ENDPOINT = "https://openrouter.ai/api/v1/key"
APPROVED_CAP_USD = Decimal("0.50")


class PaidTestBudgetError(RuntimeError):
    pass


def checked_limit(data: object) -> tuple[Decimal, Decimal]:
    """Only the provider's enforced per-key limit can authorize a test."""
    if not isinstance(data, dict) or not isinstance(data.get("data"), dict):
        raise PaidTestBudgetError("Provider key budget response unavailable")
    key = data["data"]
    raw_limit, raw_remaining = key.get("limit"), key.get("limit_remaining")
    if (type(raw_limit) not in (int, float, str) or
            type(raw_remaining) not in (int, float, str)):
        raise PaidTestBudgetError("Provider per-key spending cap is missing")
    try:
        limit = Decimal(str(raw_limit))
        remaining = Decimal(str(raw_remaining))
    except InvalidOperation as exc:
        raise PaidTestBudgetError("Invalid provider budget") from exc
    if not (limit.is_finite() and remaining.is_finite() and
            Decimal("0") < limit <= APPROVED_CAP_USD and
            Decimal("0") < remaining <= limit):
        raise PaidTestBudgetError("Provider key limit is not within the approved $0.50 cap")
    return limit, remaining


async def require_paid_test_cap(client: httpx.AsyncClient, key: str) -> tuple[Decimal, Decimal]:
    if not key:
        raise PaidTestBudgetError("Provider key missing")
    try:
        response = await client.get(
            KEY_ENDPOINT,
            headers={"Authorization": "Bearer " + key},
            timeout=8,
            follow_redirects=False,
        )
        if response.status_code != 200:
            raise PaidTestBudgetError("Provider budget verification failed")
        return checked_limit(response.json())
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        raise PaidTestBudgetError("Provider budget verification unavailable") from exc
