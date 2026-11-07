"""PostgreSQL-atomic personal spending reservations, conservative on errors."""
import hashlib
import hmac
import os
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_CEILING

import asyncpg

SCHEMA = """
CREATE TABLE IF NOT EXISTS personal_daily_quota (
    subject_hash text NOT NULL, day_utc date NOT NULL,
    reserved_micro_usd bigint NOT NULL DEFAULT 0,
    request_count integer NOT NULL DEFAULT 0,
    PRIMARY KEY (subject_hash, day_utc)
);
"""


class BudgetExceeded(RuntimeError):
    pass


def hash_principal(issuer: str, subject: str):
    key = os.getenv("DRAGONZPYDER_PERSONAL_ID_HASH_KEY", "")
    if len(key) < 40:
        raise RuntimeError("Identity hash key missing")
    return hmac.new(key.encode(), (issuer + "\x00" + subject).encode(),
                    hashlib.sha256).hexdigest()


def cap_micro():
    limit = Decimal(os.getenv("DRAGONZPYDER_PERSONAL_DAILY_CAP_USD", "0.03"))
    if not limit.is_finite() or not Decimal("0") < limit <= Decimal("1"):
        raise RuntimeError("Daily limit invalid")
    return int((limit * 1_000_000).to_integral_value(rounding=ROUND_CEILING))


@dataclass(frozen=True)
class Reservation:
    subject_hash: str
    day: date
    micro: int


class Budget:
    def __init__(self):
        self.pool = None

    async def start(self, dsn: str):
        if not dsn:
            raise RuntimeError("Personal budget DB required")
        self.pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=3,
                                              command_timeout=7)
        async with self.pool.acquire() as conn:
            await conn.execute(SCHEMA)

    async def stop(self):
        if self.pool is not None:
            await self.pool.close()
            self.pool = None

    async def reserve(self, subject_hash, micro):
        if self.pool is None:
            raise RuntimeError("Budget store unavailable")
        if not 1 <= micro <= 1_000_000:
            raise BudgetExceeded("Per-request cost ceiling exceeded")
        maximum_calls = int(os.getenv("DRAGONZPYDER_PERSONAL_CALLS_PER_DAY", "25"))
        if not 1 <= maximum_calls <= 200:
            raise RuntimeError("Invalid request cap")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """INSERT INTO personal_daily_quota(subject_hash,day_utc)
                       VALUES($1,(now() AT TIME ZONE 'UTC')::date)
                       ON CONFLICT DO NOTHING""", subject_hash)
                row = await conn.fetchrow(
                    """SELECT day_utc,reserved_micro_usd,request_count
                       FROM personal_daily_quota WHERE subject_hash=$1
                       AND day_utc=(now() AT TIME ZONE 'UTC')::date
                       FOR UPDATE""", subject_hash)
                if (row["request_count"] >= maximum_calls or
                        row["reserved_micro_usd"] + micro > cap_micro()):
                    raise BudgetExceeded("Personal daily budget reached")
                await conn.execute(
                    """UPDATE personal_daily_quota
                       SET reserved_micro_usd=reserved_micro_usd+$3,
                           request_count=request_count+1
                       WHERE subject_hash=$1 AND day_utc=$2""",
                    subject_hash, row["day_utc"], micro)
                return Reservation(subject_hash, row["day_utc"], micro)

    async def settle(self, hold: Reservation, cost_usd):
        # Missing/invalid cost keeps the entire reservation, never $0.
        if cost_usd is None:
            return
        amount = Decimal(str(cost_usd))
        if not amount.is_finite() or amount < 0:
            return
        actual = int((amount * 1_000_000).to_integral_value(rounding=ROUND_CEILING))
        if actual == hold.micro:
            return
        async with self.pool.acquire() as conn:
            await conn.execute(
                """UPDATE personal_daily_quota
                   SET reserved_micro_usd=GREATEST(0,reserved_micro_usd+$3)
                   WHERE subject_hash=$1 AND day_utc=$2""",
                hold.subject_hash, hold.day, actual - hold.micro)

    async def summary(self, subject_hash):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT request_count,reserved_micro_usd
                   FROM personal_daily_quota WHERE subject_hash=$1
                   AND day_utc=(now() AT TIME ZONE 'UTC')::date""",
                subject_hash)
        used = row["reserved_micro_usd"] if row else 0
        maximum = cap_micro()
        return {"daily_cap_usd": str(Decimal(maximum) / 1_000_000),
                "spent_or_reserved_usd": str(Decimal(used) / 1_000_000),
                "remaining_usd": str(Decimal(max(0, maximum-used)) / 1_000_000),
                "requests_today": row["request_count"] if row else 0}
