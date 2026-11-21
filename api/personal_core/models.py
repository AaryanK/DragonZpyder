"""Cost-first selection over operator-approved OpenRouter catalog models."""
import asyncio
import os
import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_CEILING

import httpx

CATALOG_URL = "https://openrouter.ai/api/v1/models"
MILLION = Decimal(1_000_000)


class ModelUnavailable(RuntimeError):
    pass


def price(value):
    try:
        n = Decimal(str(value))
        return n if n.is_finite() and n >= 0 else None
    except (ValueError, TypeError, InvalidOperation):
        return None


@dataclass(frozen=True)
class Choice:
    model: str
    reserve_micro_usd: int
    estimated_cost_usd: Decimal


def approved_models():
    raw = os.getenv("DRAGONZPYDER_PERSONAL_ALLOWED_MODELS", "")
    allowed = {x.strip() for x in raw.split(",") if x.strip()}
    if len(allowed) > 12 or any(len(x) > 100 or not all(
        c.isalnum() or c in "_./:-" for c in x
    ) for x in allowed):
        raise ModelUnavailable("Personal model allowlist is invalid")
    return allowed


def choose(entries, allowed, *, input_bytes, output_tokens,
           input_cap_m=Decimal("0.25"), output_cap_m=Decimal("1.5")):
    if not isinstance(entries, list) or not allowed:
        raise ModelUnavailable("No approved model catalog")
    found = []
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("id") not in allowed:
            continue
        arch = entry.get("architecture", {})
        if not isinstance(arch, dict) or not (
            "text" in arch.get("input_modalities", [])
            and "text" in arch.get("output_modalities", [])
        ):
            continue
        context = entry.get("context_length")
        if type(context) is not int or context < input_bytes + output_tokens + 256:
            continue
        pricing = entry.get("pricing", {})
        if not isinstance(pricing, dict):
            continue
        pi, po, fixed = (price(pricing.get("prompt")),
                         price(pricing.get("completion")),
                         price(pricing.get("request", "0")))
        if pi is None or po is None or fixed is None:
            continue
        if pi * MILLION > input_cap_m or po * MILLION > output_cap_m:
            continue
        # Conservative text-token upper bound, including framing overhead.
        conservative_input = input_bytes + 256
        estimate = pi * conservative_input + po * output_tokens + fixed
        ceiling = (input_cap_m * conservative_input / MILLION
                   + output_cap_m * output_tokens / MILLION + fixed)
        hold = int((ceiling * MILLION).to_integral_value(rounding=ROUND_CEILING))
        found.append((estimate, entry["id"], max(1, hold)))
    if not found:
        raise ModelUnavailable("No approved model within price and context limits")
    estimated, name, reservation = min(found)
    return Choice(name, reservation, estimated)


class Catalog:
    def __init__(self):
        self._models = None
        self._expires = 0.0
        self._lock = asyncio.Lock()

    async def get(self, client: httpx.AsyncClient):
        if self._models is not None and time.monotonic() < self._expires:
            return self._models
        async with self._lock:
            if self._models is not None and time.monotonic() < self._expires:
                return self._models
            try:
                response = await client.get(CATALOG_URL, timeout=12)
                response.raise_for_status()
                document = response.json()
                records = document["data"]
                if not isinstance(records, list) or len(records) > 10000:
                    raise ValueError("Unexpected catalog")
            except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
                raise ModelUnavailable("Live model pricing unavailable") from exc
            self._models = records
            self._expires = time.monotonic() + 600
            return records
