"""Authenticated parent-budget gateway adapter for opt-in staging parallel agents.

Only the gateway owns this PostgreSQL store and OpenRouter key. Each request
reserves atomically BEFORE model dispatch; unknown outcomes retain their hold.
No parallel paid execution is enabled by merely importing this module.
"""
from __future__ import annotations
import os
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from uuid import UUID

from .budget_reservations import AtomicBudgetStore, SCHEMA, BudgetExceeded, amount

TENANT = "agent-runtime"
MAX_PARENT_USD = Decimal("0.50")
MAX_INPUT_PRICE_PER_M = Decimal("1.0")
MAX_OUTPUT_PRICE_PER_M = Decimal("4.0")
QUANTUM = Decimal("0.0000000001")


def conservative_request_ceiling(*, payload_bytes: int, output_tokens: int) -> str:
    """Price cap upper-bound: count every UTF-8 byte as an input token.

    This estimate is used only when the gateway also sets provider.max_price
    and requires reported usage; any unknown/above-hold cost stays reserved.
    """
    if (type(payload_bytes) is not int or not 1 <= payload_bytes <= 160000
            or type(output_tokens) is not int or not 1 <= output_tokens <= 4096):
        raise ValueError("Inference request bounds invalid")
    usd = (
        Decimal(payload_bytes)*MAX_INPUT_PRICE_PER_M
        + Decimal(output_tokens)*MAX_OUTPUT_PRICE_PER_M
    ) / Decimal(1000000) + Decimal("0.0002")
    return str(usd.quantize(QUANTUM, rounding=ROUND_CEILING))


def audited_provider_cost(response: object) -> str | None:
    """Return an authoritative nonnegative provider usage.cost or None.

    Missing/nonfinite/malformed costs are NOT treated as zero.
    """
    if not isinstance(response, dict):
        return None
    usage = response.get("usage")
    if not isinstance(usage, dict):
        return None
    raw = usage.get("cost")
    if isinstance(raw, bool) or not isinstance(raw, (int,float,str,Decimal)):
        return None
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if not value.is_finite() or value < 0 or value > MAX_PARENT_USD:
        return None
    return "0" if value == 0 else str(value.quantize(QUANTUM, rounding=ROUND_CEILING))


def _id(raw: str) -> str:
    try:
        canonical = str(UUID(raw))
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Invalid budget UUID") from None
    if canonical != raw:
        raise ValueError("Noncanonical budget UUID")
    return canonical


class ParentBudgetGateway:
    """Staging-only facade over transactional budget store."""
    def __init__(self):
        self.pool = None
        self.store = None

    @property
    def active(self) -> bool:
        return self.store is not None

    async def open(self) -> None:
        if not (
            os.getenv("DRAGONZPYDER_AGENT_PARALLEL_GATEWAY_ENABLED") == "1"
            and os.getenv("RAILWAY_ENVIRONMENT_NAME") == "staging"
            and os.getenv("DRAGONZPYDER_STAGING_PAID_TEST_CAP_USD") == "0.50"
        ):
            return
        dsn = os.getenv("DRAGONZPYDER_AGENT_SHARED_BUDGET_DATABASE_URL", "")
        if not dsn.startswith(("postgres://","postgresql://")):
            return
        import asyncpg
        try:
            self.pool = await asyncpg.create_pool(dsn=dsn,min_size=1,max_size=4,
                                                  timeout=8,command_timeout=8)
            async with self.pool.acquire() as con:
                await con.execute(SCHEMA)
            self.store = AtomicBudgetStore(self.pool)
        except Exception:
            await self.close()
            raise RuntimeError("Parent budget gateway database unavailable") from None

    async def close(self):
        self.store = None
        if self.pool is not None:
            await self.pool.close()
            self.pool = None

    async def create(self, *, job_id: str, ceiling_usd: str):
        if not self.active:
            raise BudgetExceeded("Gateway-enforced parent budget not configured")
        job = _id(job_id)
        ceiling = amount(ceiling_usd)
        if ceiling > MAX_PARENT_USD:
            raise BudgetExceeded("Parent budget exceeds approved $0.50 cap")
        await self.store.create_job(job_id=job,tenant_id=TENANT,
                                    ceiling_usd=str(ceiling))

    async def reserve(self, *, job_id: str, request_id: str,
                      payload_bytes: int, output_tokens: int):
        if not self.active:
            raise BudgetExceeded("Gateway-enforced parent budget not configured")
        ceiling=conservative_request_ceiling(
            payload_bytes=payload_bytes,output_tokens=output_tokens)
        created=await self.store.reserve(job_id=_id(job_id),tenant_id=TENANT,
                                          request_id=_id(request_id),
                                          estimate_usd=ceiling)
        if not created:
            raise BudgetExceeded("Duplicate inference request; replay refused")
        return ceiling

    async def settle(self, *, job_id: str, request_id: str,
                     provider_response: object) -> bool:
        """Unknown provider cost: hold retained and return False."""
        if not self.active:
            return False
        cost=audited_provider_cost(provider_response)
        try:
            return await self.store.settle(job_id=_id(job_id),tenant_id=TENANT,
                          request_id=_id(request_id),actual_usd=cost)
        except BudgetExceeded:
            # Unknown cost remains held durably. Never silently release.
            return False

    async def settle_known_rejection(self, *, job_id: str, request_id: str):
        """Only a known HTTP 429 upstream rejection is free to release."""
        if not self.active:
            return False
        return await self.store.settle(job_id=_id(job_id),tenant_id=TENANT,
                                        request_id=_id(request_id),actual_usd="0")
