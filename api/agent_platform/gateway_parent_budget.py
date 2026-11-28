"""Authenticated parent-budget gateway adapter for bounded agent execution.

Only the gateway owns this PostgreSQL store and OpenRouter key. Each request
reserves atomically BEFORE model dispatch; unknown outcomes retain their hold.
No parallel paid execution is enabled by merely importing this module.
"""
from __future__ import annotations
import os
import re
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


def deployment_admitted() -> bool:
    """Reuse the existing durable workflow rollout gate in production."""
    if os.getenv("DRAGONZPYDER_AGENT_PARALLEL_GATEWAY_ENABLED") != "1":
        return False
    environment = os.getenv("RAILWAY_ENVIRONMENT_NAME")
    if environment == "staging":
        return os.getenv("DRAGONZPYDER_STAGING_PAID_TEST_CAP_USD") == "0.50"
    if environment == "production":
        return os.getenv("DRAGONZPYDER_NATIVE_DURABLE_WORKFLOWS_ENABLED") == "1"
    return False


class ParentBudgetGateway:
    """Transactional budget store; provider cap is independently verified."""
    def __init__(self):
        self.pool = None
        self.store = None

    @property
    def active(self) -> bool:
        return self.store is not None

    async def open(self) -> None:
        if not deployment_admitted():
            return
        dsn = os.getenv("DRAGONZPYDER_AGENT_SHARED_BUDGET_DATABASE_URL", "")
        # Staging may explicitly choose the same trusted PostgreSQL cluster
        # as the gateway usage ledger. Both ledgers use distinct table names;
        # the browser and model never supply the DSN.
        if (not dsn
                and os.getenv("DRAGONZPYDER_AGENT_PARALLEL_USE_USAGE_DB") == "1"):
            dsn = os.getenv("DRAGONZPYDER_USAGE_DATABASE_URL", "")
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
            # Fail closed for paid fan-out without taking ordinary staging
            # inference offline when the reservation database is unavailable.
            return

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

    async def reconcile(self, *, job_id: str, ledger, http, key: str) -> int:
        """Reconcile this parent's holds only from gateway-owned usage evidence.

        No new inference, untrusted cost estimates, or releases on missing
        evidence. Lookups use provider generation IDs recorded by this gateway.
        Bounded per admission attempt; unknown/in-flight work stays held.
        """
        if not self.active or self.pool is None or getattr(ledger,"pool",None) is None:
            return 0
        job=UUID(_id(job_id))
        async with self.pool.acquire() as con:
            pending=await con.fetch("""SELECT request_id FROM agent_budget_reservations
                WHERE job_id=$1 AND tenant_id=$2 AND status IN ('unknown','reserved')
                ORDER BY request_id LIMIT 16""",job,TENANT)
        if not pending:
            return 0
        async with ledger.pool.acquire() as con:
            rows=await con.fetch("""SELECT request_id,provider_generation_id,provider_cost_usd
                FROM model_usage_events WHERE request_id=ANY($1::uuid[])
                AND app_id='agent-runtime' AND provider='openrouter'
                AND provider_generation_id IS NOT NULL""",
                [row["request_id"] for row in pending])
        resolved=0
        lookups=0
        for row in rows:
            generation=row["provider_generation_id"]
            if not isinstance(generation,str) or not re.fullmatch(r"gen-[A-Za-z0-9_-]{1,120}",generation):
                continue
            cost=audited_provider_cost({"usage":{"cost":row["provider_cost_usd"]}})
            if cost is None and lookups<4 and key:
                lookups+=1
                try:
                    response=await http.get("https://openrouter.ai/api/v1/generation",
                        params={"id":generation},headers={"Authorization":"Bearer "+key},
                        timeout=2,follow_redirects=False)
                    if response.status_code!=200 or len(response.content)>65536:
                        continue
                    data=response.json().get("data")
                    if not isinstance(data,dict) or data.get("id")!=generation:
                        continue
                    cost=audited_provider_cost({"usage":{"cost":data.get("total_cost")}})
                except Exception:
                    continue
            if cost is None:
                continue
            try:
                if await self.store.settle(job_id=str(job),tenant_id=TENANT,
                        request_id=str(row["request_id"]),actual_usd=cost):
                    resolved+=1
            except BudgetExceeded:
                # Concurrent settlement, above-bound charge, or conflicting
                # evidence: retain the remaining hold, never overwrite it.
                continue
        return resolved

    async def accounting_snapshot(self, job_id: str) -> dict:
        """Private, read-only accounting diagnostics; never free unknown holds."""
        if not self.active:
            return {"available": False}
        async with self.pool.acquire() as con:
            row=await con.fetchrow("""SELECT b.ceiling_usd,b.reserved_usd,b.settled_usd,
                (SELECT count(*) FROM agent_budget_reservations r
                 WHERE r.job_id=b.job_id AND r.tenant_id=b.tenant_id
                 AND r.status='unknown') AS unknown_count
                FROM agent_job_budgets b WHERE b.job_id=$1 AND b.tenant_id=$2""",
                UUID(_id(job_id)),TENANT)
        if row is None:
            return {"available": False}
        return {"available":True,"ceiling_usd":str(row["ceiling_usd"]),
                "reserved_usd":str(row["reserved_usd"]),"settled_usd":str(row["settled_usd"]),
                "unknown_count":row["unknown_count"]}

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
