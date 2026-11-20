"""Hatchet scheduling adapter; no homegrown queue or scheduler.

Jobs are test-service scoped until DragonZpyder issues signed per-user
execution delegations. Do not connect user-facing schedule creation yet.
"""
from __future__ import annotations

from datetime import timedelta
import os
from urllib.parse import urlsplit

import httpx

from pydantic import BaseModel, Field


class AgentJobInput(BaseModel):
    thread_id: str = Field(pattern=r"^[a-zA-Z0-9_.-]{1,80}$")
    prompt: str = Field(min_length=1, max_length=12000)



class PingInput(BaseModel):
    message: str = Field(default="hello", min_length=1, max_length=64)


class PingOutput(BaseModel):
    ok: bool
    message: str


def make_ping_task(hatchet):
    """Small, zero-inference acceptance task for Hatchet scheduling."""
    @hatchet.task(
        name="dragonzpyder-staging-ping",
        input_validator=PingInput,
        retries=0,
        concurrency=1,
    )
    async def ping(input: PingInput, ctx) -> PingOutput:
        return PingOutput(ok=True, message=input.message)

    return ping



async def delegate_agent_job_to_api(input: AgentJobInput, *, client=None) -> dict[str, str]:
    """Opt-in Hatchet -> private DragonZpyder agent API. Never falls back.

    This still uses only the experimental service-scoped agent principal,
    not a personal or workspace identity. No user data can be scheduled here.
    """
    endpoint = os.getenv("DRAGONZPYDER_HATCHET_AGENT_API_URL", "").strip()
    token = os.getenv("DRAGONZPYDER_AGENT_SERVICE_TOKEN", "")
    parsed = urlsplit(endpoint)
    private = (parsed.scheme == "http" and bool(parsed.hostname)
               and parsed.hostname.endswith(".railway.internal")
               and parsed.port in (None, 8080))
    public = (parsed.scheme == "https" and
              parsed.hostname == "api.dragonzpyder.xyz" and
              parsed.port in (None, 443))
    if (not (private or public) or parsed.path != "/internal/agents/run"
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or len(token) < 40):
        raise RuntimeError("Private agent API delegation is not configured")
    request = {"thread_id": input.thread_id, "prompt": input.prompt}
    async def perform(transport):
        try:
            response = await transport.post(
                endpoint, json=request,
                headers={"Authorization": "Bearer " + token},
                timeout=90.0, follow_redirects=False,
            )
        except httpx.HTTPError as error:
            raise RuntimeError("Private agent API unavailable") from None
        if response.status_code != 200 or len(response.content) > 20000:
            raise RuntimeError("Private agent API rejected execution")
        try:
            body = response.json()
        except ValueError:
            raise RuntimeError("Private agent API returned invalid JSON") from None
        if (not isinstance(body, dict) or body.get("thread_id") != input.thread_id
                or not isinstance(body.get("answer"), str)):
            raise RuntimeError("Private agent API returned invalid result")
        return {"thread_id": input.thread_id, "answer": body["answer"][:16000]}
    if client is not None:
        return await perform(client)
    async with httpx.AsyncClient(trust_env=False) as transport:
        return await perform(transport)


async def install_staging_agent_ping_cron(task):
    """An explicitly authorized five-minute *zero-model* Hatchet test schedule."""
    if (os.getenv("DRAGONZPYDER_STAGE") != "staging"
            or os.getenv("DRAGONZPYDER_STAGING_HATCHET_PING_CRON_ALLOWED") != "1"):
        raise RuntimeError("Five-minute Hatchet ping cron is not authorized")
    return await task.aio_create_cron(
        cron_name="dragonzpyder-staging-ping-5m-v1",
        expression="*/5 * * * *",
        input=PingInput(message="staging-cron-health"),
    )


def make_agent_task(hatchet):
    """Return a Hatchet task that can run, schedule, or create a cron."""
    from .runtime import AgentRuntime

    @hatchet.task(
        name="dragonzpyder-internal-agent",
        input_validator=AgentJobInput,
        concurrency=2,
        retries=0,
        execution_timeout=timedelta(minutes=5),
    )
    async def execute(input: AgentJobInput, ctx) -> dict[str, str]:
        if os.getenv("DRAGONZPYDER_AGENT_HATCHET_USE_API") == "1":
            return await delegate_agent_job_to_api(input)
        runtime = AgentRuntime()
        await runtime.start()
        try:
            result = await runtime.run(
                service_id="agent-smoke",
                thread_id=input.thread_id,
                prompt=input.prompt,
            )
            return {"thread_id": input.thread_id, "answer": result}
        finally:
            await runtime.close()

    return execute
