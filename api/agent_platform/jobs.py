"""Hatchet scheduling adapter; no homegrown queue or scheduler.

Jobs are test-service scoped until DragonZpyder issues signed per-user
execution delegations. Do not connect user-facing schedule creation yet.
"""
from __future__ import annotations

from datetime import timedelta

from pydantic import BaseModel, Field


class AgentJobInput(BaseModel):
    thread_id: str = Field(pattern=r"^[a-zA-Z0-9_.-]{1,80}$")
    prompt: str = Field(min_length=1, max_length=12000)



class PingInput(BaseModel):
    message: str = Field(default="hello", min_length=1, max_length=64)


def make_ping_task(hatchet):
    """Small, zero-inference acceptance task for Hatchet scheduling."""
    @hatchet.task(
        name="dragonzpyder-staging-ping",
        input_validator=PingInput,
        retries=0,
        concurrency=1,
    )
    async def ping(input: PingInput, ctx):
        return {"ok": True, "message": input.message}

    return ping


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
    async def execute(input: AgentJobInput, ctx):
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
