"""Temporary DragonZpyder-owned clock for the Operly workflow migration.

The Hatchet task wakes Operly's existing leased compatibility executor.
It does not assume that an accepted wake means workflow completion.
No model, user data, arbitrary URLs or cron registration on import.
"""
from __future__ import annotations

import asyncio
from datetime import timedelta
import os

import httpx
from pydantic import BaseModel, ConfigDict

ENDPOINT = "https://operly.dragonzpyder.xyz/api/internal/dragonzpyder/workflow-dispatch"
TASK_NAME = "dragonzpyder-operly-workflow-compat-dispatch"
CRON_NAME = "dragonzpyder-operly-workflow-compat-minute-v1"


class DispatchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


def require_dispatch_gate() -> str:
    if os.getenv("DRAGONZPYDER_OPERLY_WORKFLOW_HANDOFF_ENABLED") != "1":
        raise RuntimeError("workflow_handoff_disabled")
    proof = os.getenv("DRAGONZPYDER_OPERLY_WORKFLOW_HANDOFF_SECRET", "")
    if not (40 <= len(proof) <= 512 and proof.isascii()):
        raise RuntimeError("workflow_handoff_secret_missing")
    return proof


async def dispatch_compatibility_tick(*, client=None) -> dict:
    proof = require_dispatch_gate()

    async def send(transport):
        try:
            response = await transport.post(
                ENDPOINT,
                headers={"X-DragonZpyder-Workflow-Proof": proof},
                timeout=30.0,
                follow_redirects=False,
            )
        except httpx.HTTPError:
            raise RuntimeError("workflow_handoff_transport_failed") from None
        if response.status_code != 200 or len(response.content) > 4096:
            raise RuntimeError("workflow_handoff_rejected")
        try:
            result = response.json()
        except ValueError:
            raise RuntimeError("workflow_handoff_invalid_receipt") from None
        if (not isinstance(result, dict)
                or result.get("driver") != "dragonzpyder"
                or result.get("dispatch") != "accepted"
                or result.get("completion_verified") is not False
                or type(result.get("queued_events")) is not int
                or type(result.get("active_workers")) is not int
                or min(result["queued_events"], result["active_workers"]) < 0):
            raise RuntimeError("workflow_handoff_invalid_receipt")
        # Only the reviewed receipt shape is returned to Hatchet.
        return {
            "driver": "dragonzpyder",
            "dispatch": "accepted",
            "queued_events": result["queued_events"],
            "active_workers": result["active_workers"],
            "completion_verified": False,
        }

    if client is not None:
        return await send(client)
    async with httpx.AsyncClient(trust_env=False, follow_redirects=False) as transport:
        return await send(transport)


def make_workflow_compat_dispatch_task(hatchet):
    require_dispatch_gate()

    @hatchet.task(
        name=TASK_NAME, input_validator=DispatchInput,
        retries=0, concurrency=1, execution_timeout=timedelta(seconds=50),
    )
    async def dispatch(input: DispatchInput, ctx) -> dict:
        return await dispatch_compatibility_tick()

    return dispatch


async def install_compatibility_cron(task):
    """Operator-only. Reconcile existing named cron before invoking.

    No cron is created by worker boot or when an agent requests a workflow.
    """
    require_dispatch_gate()
    if os.getenv("DRAGONZPYDER_WORKFLOW_HANDOFF_CRON_INSTALL_ALLOWED") != "1":
        raise RuntimeError("workflow_handoff_cron_install_not_approved")
    return await task.aio_create_cron(
        cron_name=CRON_NAME, expression="* * * * *", input=DispatchInput(),
    )


async def _operator_install():
    from hatchet_sdk import Hatchet
    task = make_workflow_compat_dispatch_task(Hatchet())
    await install_compatibility_cron(task)


if __name__ == "__main__":
    import sys
    if sys.argv[1:] != ["--install-cron"]:
        raise SystemExit("Use --install-cron only after reviewed cutover readiness")
    asyncio.run(_operator_install())
