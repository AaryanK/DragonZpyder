"""Hatchet worker task for account-scoped live activity in DragonZpyder Web.

No prompts or credentials enter Hatchet inputs. A worker retrieves encrypted
task input from PostgreSQL after an exclusive claim, emits sanitized activity,
and executes the existing LangGraph harness for explicitly budgeted tasks.
"""
from __future__ import annotations

import hashlib
import os
from datetime import timedelta

from pydantic import BaseModel, Field


class WebTaskInput(BaseModel):
    task_id: str = Field(pattern=r"^[a-f0-9-]{36}$")


def require_web_task_gate() -> None:
    if (os.getenv("DRAGONZPYDER_WEB_TASKS_ENABLED") != "1"
            or os.getenv("DRAGONZPYDER_GOAL_STORE_ENABLED") != "1"
            or os.getenv("RAILWAY_ENVIRONMENT_NAME") != "staging"):
        raise RuntimeError("Live web tasks are not enabled in isolated staging")
    if not os.getenv("DRAGONZPYDER_GOALS_DATABASE_URL", "").startswith(
        ("postgres://", "postgresql://")
    ):
        raise RuntimeError("Persistent task database is required")


class ActivityTrace:
    """LangChain callback wrapper. Never stores arguments, prompts or reasoning."""

    def __init__(self, store, task_id: str):
        self.store = store
        self.task_id = task_id

    def handler(self):
        from langchain_core.callbacks import AsyncCallbackHandler
        parent = self

        class SanitizedEvents(AsyncCallbackHandler):
            async def on_llm_start(self, serialized, prompts, **kwargs):
                await parent.safe("model_started", "Model inference started")

            async def on_chat_model_start(self, serialized, messages, **kwargs):
                await parent.safe("model_started", "Model inference started")

            async def on_llm_end(self, response, **kwargs):
                await parent.safe("model_finished", "Model inference completed")

            async def on_llm_error(self, error, **kwargs):
                await parent.safe("info", "Model inference did not complete")

            async def on_tool_start(self, serialized, input_str, **kwargs):
                # Tool names and arguments may be attacker-controlled, so do
                # not copy them into the shared ops log.
                await parent.safe("tool_started", "Agent tool started")

            async def on_tool_end(self, output, **kwargs):
                await parent.safe("tool_finished", "Agent tool returned")

            async def on_tool_error(self, error, **kwargs):
                await parent.safe("info", "Agent tool reported an error")

        return SanitizedEvents()

    async def safe(self, kind: str, message: str) -> None:
        try:
            await self.store.append(self.task_id, kind, message)
        except Exception:
            # Logging failures must not turn a successful external action into
            # an ambiguous retry; the task ledger remains authoritative.
            pass


async def execute_web_task(task_id: str) -> dict:
    require_web_task_gate()
    import asyncpg
    from .task_activity import ActivityStore, uuid

    pool = await asyncpg.create_pool(
        dsn=os.environ["DRAGONZPYDER_GOALS_DATABASE_URL"], min_size=1, max_size=3
    )
    try:
        store = ActivityStore(
            pool, encryption_key=os.environ["DRAGONZPYDER_GOALS_ENCRYPTION_KEY"]
        )
        claim = await store.claim(task_id)
        if claim is None:
            return {"status": "not_claimable"}
        task, token = claim
        await store.append(task_id, "started", "Worker accepted the task")
        await store.append(task_id, "checkpoint", "Durable task state loaded")
        try:
            if task["kind"] == "probe":
                await store.append(task_id, "info", "Running zero-cost readiness check")
                async with pool.acquire() as con:
                    ready = await con.fetchval("SELECT 1")
                if ready != 1:
                    raise RuntimeError("Readiness check did not complete")
                answer = "Task ledger and Hatchet worker are reachable. No model or external tools were used."
                status = "completed"
                trace_id = None
            else:
                if (os.getenv("DRAGONZPYDER_WEB_TASKS_PAID_ENABLED") != "1"
                        or os.getenv("DRAGONZPYDER_AGENT_USE_GATEWAY") != "1"
                        or os.getenv("DRAGONZPYDER_AGENT_PARALLEL_GATEWAY_ENABLED") != "1"):
                    raise RuntimeError("Budgeted reasoning is not enabled")
                from .runtime import AgentRuntime
                runtime = AgentRuntime()
                try:
                    await runtime.start()
                    await store.append(task_id, "model_started",
                                       "Checkpointed LangGraph harness started")
                    prompt = store.cipher.decrypt(
                        bytes(task["prompt_ciphertext"])
                    ).decode("utf-8")
                    # Thread is tied to the task and owner, never shared among
                    # accounts. Parent budget is transactionally metered by
                    # the gateway before EACH provider request.
                    owner_service = "web-" + task["owner_hash"][:32]
                    report = await runtime.run_report(
                        service_id=owner_service,
                        thread_id=task_id,
                        prompt=prompt,
                        parent_job_id=task_id,
                        recover_partial_on_failure=True,
                        activity_callbacks=[ActivityTrace(store, task_id).handler()],
                    )
                    answer = str(report.get("answer") or "")
                    status = ("completed" if report.get("status") == "completed"
                              else "incomplete")
                    trace_id = report.get("langfuse_trace_id")
                    await store.append(task_id, "checkpoint",
                                       "LangGraph checkpoint and summary recorded")
                finally:
                    await runtime.close()
            committed = await store.finish(
                task_id=task_id, claim_token=token,
                status=status, answer=answer, trace_id=trace_id,
            )
            if committed:
                await store.append(
                    task_id, "completed" if status == "completed" else "incomplete",
                    "Task completed" if status == "completed"
                    else "Task stopped before verified completion",
                )
            return {"status": status if committed else "stale_or_cancelled",
                    "objective_verified": False}
        except Exception:
            # Do not place provider exception text or user prompts in the log.
            committed = await store.finish(
                task_id=task_id, claim_token=token, status="failed",
            )
            if committed:
                await store.append(task_id, "failed", "Task failed; inspect server diagnostics")
            return {"status": "failed" if committed else "stale_or_cancelled",
                    "objective_verified": False}
    finally:
        await pool.close()


def make_web_task(hatchet):
    @hatchet.task(
        name="dragonzpyder-web-harness-v1",
        input_validator=WebTaskInput,
        concurrency=1,
        retries=0,
        execution_timeout=timedelta(minutes=6),
    )
    async def work(input: WebTaskInput, ctx) -> dict:
        return await execute_web_task(input.task_id)

    return work
