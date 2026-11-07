"""Transactional budget reservation primitive for a future authenticated gateway.

Not wired into live inference. A gateway must authenticate the tenant/job and
bind every child request to a reservation before paid fan-out can be enabled.
Amounts are upper-bound USD estimates, never post-hoc provider usage guesses.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from uuid import UUID

# All monetary arithmetic occurs inside PostgreSQL transactions, never from a
# local Python process counter. Unknown provider costs retain their hold.
SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_job_budgets (
  job_id uuid PRIMARY KEY,
  tenant_id text NOT NULL,
  ceiling_usd numeric(20,10) NOT NULL CHECK (ceiling_usd > 0),
  reserved_usd numeric(20,10) NOT NULL DEFAULT 0
    CHECK (reserved_usd >= 0),
  settled_usd numeric(20,10) NOT NULL DEFAULT 0
    CHECK (settled_usd >= 0),
  CHECK (reserved_usd + settled_usd <= ceiling_usd)
);
CREATE TABLE IF NOT EXISTS agent_budget_reservations (
  request_id uuid PRIMARY KEY,
  job_id uuid NOT NULL REFERENCES agent_job_budgets(job_id),
  tenant_id text NOT NULL,
  estimate_usd numeric(20,10) NOT NULL CHECK (estimate_usd > 0),
  actual_usd numeric(20,10),
  status text NOT NULL DEFAULT 'reserved'
    CHECK (status IN ('reserved', 'settled', 'unknown')),
  CHECK (actual_usd IS NULL OR actual_usd >= 0)
);
"""

QUANTUM = Decimal("0.0000000001")
MAX_USD = Decimal("1000000")


def amount(value: object) -> Decimal:
    """Reject floats, booleans, negative, zero, non-finite and excess precision."""
    if not isinstance(value, (str, Decimal)):
        raise ValueError("USD amount must be a decimal string")
    try:
        parsed = Decimal(value)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("Invalid USD amount") from exc
    if (not parsed.is_finite() or not 0 < parsed <= MAX_USD
            or parsed.as_tuple().exponent < -10):
        raise ValueError("USD amount outside allowed range or precision")
    return parsed.quantize(QUANTUM)


def nonnegative_amount(value: object) -> Decimal:
    if value in ("0", Decimal("0")):
        return Decimal("0").quantize(QUANTUM)
    return amount(value)


def identity(value: str) -> UUID:
    try:
        result = UUID(value)
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("Invalid UUID") from exc
    if str(result) != value:
        raise ValueError("UUID must use canonical lowercase format")
    return result


class BudgetExceeded(RuntimeError):
    pass


class AtomicBudgetStore:
    """Database primitive only. Caller must authenticate tenant and job.

    No external inference may be made before reserve() returns successfully.
    The gateway must not release holds on timeout or unknown provider outcome.
    """

    def __init__(self, pool):
        self.pool = pool

    async def create_job(self, *, job_id: str, tenant_id: str, ceiling_usd: str) -> None:
        job, ceiling = identity(job_id), amount(ceiling_usd)
        if not isinstance(tenant_id, str) or not 1 <= len(tenant_id) <= 128:
            raise ValueError("Invalid tenant")
        async with self.pool.acquire() as con:
            # Replays never raise an existing ceiling, even if caller changes it.
            result = await con.fetchrow(
                """INSERT INTO agent_job_budgets(job_id,tenant_id,ceiling_usd)
                   VALUES($1,$2,$3) ON CONFLICT(job_id) DO NOTHING
                   RETURNING tenant_id,ceiling_usd""", job, tenant_id, ceiling)
            if result is None:
                result = await con.fetchrow(
                    """SELECT tenant_id,ceiling_usd FROM agent_job_budgets
                       WHERE job_id=$1""", job)
            if result is None or result["tenant_id"] != tenant_id or result["ceiling_usd"] != ceiling:
                raise BudgetExceeded("Conflicting budget identity or ceiling")

    async def reserve(self, *, job_id: str, tenant_id: str, request_id: str,
                      estimate_usd: str) -> bool:
        job, request, estimate = identity(job_id), identity(request_id), amount(estimate_usd)
        if not isinstance(tenant_id, str) or not 1 <= len(tenant_id) <= 128:
            raise ValueError("Invalid tenant")
        async with self.pool.acquire() as con:
            async with con.transaction():
                # Lock the parent FIRST. This serializes all child reservations
                # under the same budget across processes and restarts.
                parent = await con.fetchrow(
                    """SELECT ceiling_usd,reserved_usd,settled_usd
                       FROM agent_job_budgets
                       WHERE job_id=$1 AND tenant_id=$2 FOR UPDATE""", job, tenant_id)
                if parent is None:
                    raise BudgetExceeded("Missing authenticated parent budget")
                previous = await con.fetchrow(
                    """SELECT job_id,tenant_id,estimate_usd,status
                       FROM agent_budget_reservations WHERE request_id=$1""", request)
                if previous is not None:
                    if (previous["job_id"] != job or previous["tenant_id"] != tenant_id
                            or previous["estimate_usd"] != estimate):
                        raise BudgetExceeded("Conflicting idempotency key")
                    # True indicates a NEW reservation only. Retried requests
                    # must not reissue paid inference without replay handling.
                    return False
                if parent["reserved_usd"] + parent["settled_usd"] + estimate > parent["ceiling_usd"]:
                    raise BudgetExceeded("Shared parent USD budget exceeded")
                await con.execute(
                    """INSERT INTO agent_budget_reservations
                       (request_id,job_id,tenant_id,estimate_usd)
                       VALUES($1,$2,$3,$4)""", request, job, tenant_id, estimate)
                await con.execute(
                    """UPDATE agent_job_budgets
                       SET reserved_usd=reserved_usd+$3
                       WHERE job_id=$1 AND tenant_id=$2""", job, tenant_id, estimate)
                return True

    async def settle(self, *, job_id: str, tenant_id: str, request_id: str,
                     actual_usd: str | None) -> bool:
        job, request = identity(job_id), identity(request_id)
        actual = nonnegative_amount(actual_usd) if actual_usd is not None else None
        async with self.pool.acquire() as con:
            async with con.transaction():
                parent = await con.fetchrow(
                    """SELECT ceiling_usd,reserved_usd,settled_usd
                       FROM agent_job_budgets WHERE job_id=$1 AND tenant_id=$2
                       FOR UPDATE""", job, tenant_id)
                if parent is None:
                    raise BudgetExceeded("Missing authenticated parent budget")
                reservation = await con.fetchrow(
                    """SELECT estimate_usd,actual_usd,status
                       FROM agent_budget_reservations
                       WHERE request_id=$1 AND job_id=$2 AND tenant_id=$3 FOR UPDATE""",
                    request, job, tenant_id)
                if reservation is None:
                    raise BudgetExceeded("Missing reservation")
                if reservation["status"] == "settled":
                    if reservation["actual_usd"] != actual:
                        raise BudgetExceeded("Conflicting settlement replay")
                    return False
                if actual is None or actual > reservation["estimate_usd"]:
                    # Provider usage unknown or exceeded the reserved bound:
                    # never release money or claim success.
                    raise BudgetExceeded("Unknown or above-reservation provider cost; hold retained")
                await con.execute(
                    """UPDATE agent_job_budgets
                       SET reserved_usd=reserved_usd-$3,
                           settled_usd=settled_usd+$4
                       WHERE job_id=$1 AND tenant_id=$2""",
                    job, tenant_id, reservation["estimate_usd"], actual)
                await con.execute(
                    """UPDATE agent_budget_reservations
                       SET status='settled',actual_usd=$2 WHERE request_id=$1""",
                    request, actual)
                return True
