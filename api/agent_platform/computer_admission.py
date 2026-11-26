"""Durable admission and reconciliation records for one scoped computer run.

These reservations cap operator-approved exposure and concurrency. They do
not invent actual provider charges or imply Railway enforces a hard lifetime.
A missing cleanup or cost receipt retains its hold until operator reconciliation.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from .budget_reservations import amount
from .computer import ComputerScope, ScopedComputerTransport
from .computer_run import ComputerRun, ComputerRunGrant


@dataclass(frozen=True)
class ComputerAdmissionPolicy:
    maximum_session_usd: str
    owner_daily_usd: str
    global_daily_usd: str
    owner_active: int = 1
    global_active: int = 4

    def __post_init__(self):
        one, owner, global_limit=map(amount,(self.maximum_session_usd,self.owner_daily_usd,self.global_daily_usd))
        if (one>owner or owner>global_limit or type(self.owner_active) is not int
                or type(self.global_active) is not int or not 1<=self.owner_active<=self.global_active<=16):
            raise ValueError("Invalid sandbox admission policy")


class ComputerAdmission:
    def __init__(self, db_factory, *, scope, run_id, policy):
        if (not isinstance(scope,ComputerScope) or scope.kind!="personal"
                or not isinstance(run_id,UUID) or not isinstance(policy,ComputerAdmissionPolicy)):
            raise ValueError("Trusted Personal computer admission required")
        self.db_factory=db_factory
        self.scope=scope
        self.run_id=run_id
        self.policy=policy

    async def reserve(self):
        # One global lock serializes both global and owner limits across
        # API replicas. This is an allocation path, not a per-token hot path.
        async with self.db_factory() as db:
            async with db.transaction():
                await db.execute("SELECT pg_advisory_xact_lock(hashtextextended($1,0))",
                                 "dragonzpyder-computer-admission-v1")
                previous=await db.fetchrow("SELECT state FROM dz_computer_allocations WHERE run_id=$1",self.run_id)
                if previous is not None:
                    raise PermissionError("Computer allocation already reserved; reconcile before retry")
                totals=await db.fetchrow("""SELECT
                    COUNT(*) FILTER (WHERE state IN ('reserved','active','uncertain')) AS active,
                    COUNT(*) FILTER (WHERE owner_id=$1 AND state IN ('reserved','active','uncertain')) AS owner_active,
                    COALESCE(SUM(held_usd) FILTER (WHERE quota_day=(now() AT TIME ZONE 'UTC')::date
                        OR state IN ('reserved','active','uncertain')),0) AS exposure,
                    COALESCE(SUM(held_usd) FILTER (WHERE owner_id=$1 AND
                        (quota_day=(now() AT TIME ZONE 'UTC')::date OR state IN ('reserved','active','uncertain'))),0) AS owner_exposure
                    FROM dz_computer_allocations""",self.scope.principal_id)
                hold=amount(self.policy.maximum_session_usd)
                if (totals["active"]>=self.policy.global_active or totals["owner_active"]>=self.policy.owner_active
                        or totals["exposure"]+hold>amount(self.policy.global_daily_usd)
                        or totals["owner_exposure"]+hold>amount(self.policy.owner_daily_usd)):
                    raise PermissionError("Sandbox allocation quota exhausted")
                await db.execute("""INSERT INTO dz_computer_allocations
                    (run_id,owner_id,client_session_id,held_usd,state)
                    VALUES($1,$2,$3,$4,'reserved')""",
                    self.run_id,self.scope.principal_id,self.scope.client_session_id,hold)

    async def allocated(self, sandbox_id):
        async with self.db_factory() as db:
            result=await db.fetchval("""UPDATE dz_computer_allocations
                SET sandbox_id=$3,state='active',updated_at=now()
                WHERE run_id=$1 AND owner_id=$2 AND state='reserved'
                RETURNING run_id""",self.run_id,self.scope.principal_id,sandbox_id)
            if result!=self.run_id:
                raise RuntimeError("Durable computer allocation evidence missing")

    async def finish(self, *, attempted, confirmed, sandbox_id):
        if not attempted:
            return
        # Cleanup confirms termination, not actual USD. Keep the worst-case
        # daily hold until trusted provider billing reconciliation.
        async with self.db_factory() as db:
            result=await db.fetchval("""UPDATE dz_computer_allocations
                SET state=$3,sandbox_id=COALESCE(sandbox_id,$4),updated_at=now()
                WHERE run_id=$1 AND owner_id=$2 AND state IN ('reserved','active','uncertain')
                RETURNING run_id""",self.run_id,self.scope.principal_id,
                "destroyed" if confirmed else "uncertain",sandbox_id)
            if result!=self.run_id:
                raise RuntimeError("Durable cleanup receipt unavailable")


def admitted_run(*, db_factory, owner, run_id, policy, transport,
                 deadline_seconds=180, max_calls=16):
    scope=ComputerScope("personal",owner,str(run_id))
    admission=ComputerAdmission(db_factory,scope=scope,run_id=run_id,policy=policy)
    return ComputerRun(transport,ComputerRunGrant(scope,max_calls=max_calls,
                       deadline_seconds=deadline_seconds),admission=admission)
