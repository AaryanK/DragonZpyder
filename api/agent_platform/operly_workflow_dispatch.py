"""One shared Hatchet wake for Operly's existing governed business workflow executor.

No LLM calls, extra scheduler service, database credentials, or user-selected
endpoints. Enable only after the Operly-side exclusive driver is tested.
The recurring task is registered by the existing DragonZpyder worker; its
cron is provisioned by an explicitly authorized operator, not on import.
"""
from __future__ import annotations

import asyncio
from datetime import timedelta
import os
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict

PATH = "/api/internal/dragonzpyder/workflow-pulse"
CRON_NAME = "dragonzpyder-operly-workflow-dispatch-v1"


class WorkflowPulseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


def require_dispatch_gate() -> tuple[str, str]:
    if os.getenv("DRAGONZPYDER_OPERLY_WORKFLOW_DISPATCH_ENABLED") != "1":
        raise RuntimeError("Shared Operly workflow dispatch is disabled")
    endpoint = os.getenv(
        "DRAGONZPYDER_OPERLY_WORKFLOW_DISPATCH_URL",
        "https://operly.dragonzpyder.xyz" + PATH,
    ).strip()
    parsed = urlsplit(endpoint)
    public = (parsed.scheme == "https"
              and parsed.hostname == "operly.dragonzpyder.xyz"
              and parsed.port in (None, 443))
    private = (os.getenv("DRAGONZPYDER_STAGE") == "staging"
               and parsed.scheme == "http"
               and parsed.hostname == "operly.railway.internal"
               and parsed.port in (None, 8080))
    secret = os.getenv("DRAGONZPYDER_OPERLY_WORKFLOW_DISPATCH_SECRET", "")
    if (not (public or private) or parsed.path != PATH
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or len(secret) < 40):
        raise RuntimeError("Invalid authenticated workflow dispatch configuration")
    if secret in {
        os.getenv("DRAGONZPYDER_OPERLY_MCP_SERVICE_SECRET", ""),
        os.getenv("DRAGONZPYDER_OPERLY_PERSONAL_AGENT_TOKEN", ""),
        os.getenv("DRAGONZPYDER_AGENT_SERVICE_TOKEN", ""),
    }:
        raise RuntimeError("Workflow dispatch secret must be independent")
    return endpoint, secret


async def dispatch_pulse(*, client=None) -> dict:
    endpoint, secret = require_dispatch_gate()
    async def perform(transport):
        try:
            response = await transport.post(
                endpoint,
                headers={"X-DragonZpyder-Workflow-Dispatch": secret},
                timeout=130, follow_redirects=False,
            )
        except httpx.HTTPError:
            # The HTTP outcome is uncertain. Existing Operly leases govern
            # recovery; do not automatically retry the business execution.
            raise RuntimeError("Operly dispatch transport unavailable") from None
        if response.status_code != 200 or len(response.content) > 2048:
            raise RuntimeError("Operly dispatch rejected the wake")
        try:
            body = response.json()
        except ValueError:
            raise RuntimeError("Invalid Operly dispatcher response") from None
        if (not isinstance(body, dict)
                or body.get("state") not in {"busy", "dispatched"}
                or type(body.get("claimed_runs")) is not int
                or not 0 <= body["claimed_runs"] <= 25
                or type(body.get("events_processed")) is not int
                or not 0 <= body["events_processed"] <= 500):
            raise RuntimeError("Invalid Operly dispatcher result")
        if body["state"] == "busy" and (body["claimed_runs"] or body["events_processed"]):
            raise RuntimeError("Invalid busy dispatcher result")
        return {k: body[k] for k in ("state", "claimed_runs", "events_processed")}
    if client is not None:
        return await perform(client)
    async with httpx.AsyncClient(trust_env=False) as transport:
        return await perform(transport)


def make_operly_workflow_pulse(hatchet):
    require_dispatch_gate()
    @hatchet.task(
        name="dragonzpyder-operly-workflow-dispatch",
        input_validator=WorkflowPulseInput,
        concurrency=1, retries=0,
        execution_timeout=timedelta(minutes=3),
    )
    async def pulse(input: WorkflowPulseInput, ctx) -> dict:
        return await dispatch_pulse()
    return pulse


async def install_workflow_cron(task):
    """Explicit cutover command. Register only once; inspect Hatchet first."""
    require_dispatch_gate()
    if os.getenv("DRAGONZPYDER_OPERLY_WORKFLOW_CRON_INSTALL_ALLOWED") != "1":
        raise RuntimeError("Operator has not authorized workflow cron installation")
    return await task.aio_create_cron(
        cron_name=CRON_NAME, expression="* * * * *", input=WorkflowPulseInput(),
    )


async def _install():
    from hatchet_sdk import Hatchet
    await install_workflow_cron(make_operly_workflow_pulse(Hatchet()))
    print("Workflow dispatch cron registration accepted")


if __name__ == "__main__":
    # Explicit operator command; not auto-run by any worker or API startup.
    import sys
    if sys.argv[1:] != ["install-cron"]:
        raise SystemExit("Usage: python -m agent_platform.operly_workflow_dispatch install-cron")
    asyncio.run(_install())
