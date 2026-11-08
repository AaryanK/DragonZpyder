"""Offline contracts for the operator's $0.50 OpenRouter staging cap."""
import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock

import httpx
import pytest

from agent_platform.openrouter_spend_guard import (
    PaidTestBudgetError, checked_limit, require_paid_test_cap,
)


def test_key_cap_must_be_enforced_upstream():
    assert checked_limit({"data": {"limit": 0.50, "limit_remaining": 0.41}}) == (
        Decimal("0.5"), Decimal("0.41")
    )
    for data in (
        {}, {"data": {}}, {"data": {"limit": None, "limit_remaining": 0.5}},
        {"data": {"limit": 1, "limit_remaining": 0.5}},
        {"data": {"limit": 0.5, "limit_remaining": 0}},
        {"data": {"limit": "NaN", "limit_remaining": 0.5}},
        {"data": {"limit": 0.5, "limit_remaining": 0.6}},
    ):
        with pytest.raises(PaidTestBudgetError):
            checked_limit(data)


def test_provider_preflight_is_get_only():
    class Response:
        status_code = 200
        def json(self):
            return {"data": {"limit": 0.5, "limit_remaining": 0.25}}
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get.return_value = Response()
    result = asyncio.run(require_paid_test_cap(client, "staging-only-test"))
    assert result[1] == Decimal("0.25")
    assert client.post.call_count == 0
    assert client.get.call_args.args[0] == "https://openrouter.ai/api/v1/key"
