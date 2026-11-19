"""DragonZpyder's deterministic, checkpoint-compatible LangGraph workflow runner.

Hatchet owns wakeups and retries. This graph owns step dependencies and
read-only capability execution. A separate authorization broker MUST validate
current user authority for every actual capability invocation.

No scheduled wait is implemented by sleeping in an agent worker. Wait nodes
pause the workflow and must be resumed via a durable Hatchet job.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from .spec import (
    WorkflowSpecError, evaluate_condition, render_value, validate_workflow_spec,
)

MAX_READ_ACTIONS = 30
MAX_RESULT_BYTES = 24_000

# Callable must return the same shape as an Operly broker /execute reply:
# {"ok": true, "result": {"...": "..."}}.
ReadExecutor = Callable[[str, dict[str, Any], str], Awaitable[dict[str, Any]]]


class WorkflowState(TypedDict, total=False):
    input: dict[str, Any]
    steps: dict[str, dict[str, Any]]
    status: str
    waiting_step: str | None
    error_code: str | None
    action_count: int


def stable_request_id(run_id: str, step_id: str) -> str:
    if not run_id or len(run_id) > 100:
        raise ValueError("Valid durable workflow run identifier is required")
    digest = hashlib.sha256((run_id + "\\0" + step_id).encode()).hexdigest()
    return "dz-wf-" + digest[:48]


def compile_readonly_workflow(
    spec: dict[str, Any],
    *,
    run_id: str,
    allowed_capabilities: frozenset[str],
    executor: ReadExecutor,
    checkpointer=None,
):
    """Compile a bounded, deterministic action DAG into a LangGraph.

    The first version serializes ready actions: no two workers can race over
    an external resource. Broker authorization, output validation, and
    idempotency remain enforced outside the graph. It does not claim that
    model-authored workflows can mutate apps safely.
    """
    normalized = validate_workflow_spec(spec)
    if len(normalized["steps"]) > MAX_READ_ACTIONS:
        raise WorkflowSpecError("Read-only workflow exceeds the safe step budget")
    if not isinstance(allowed_capabilities, frozenset):
        raise TypeError("Allowed capabilities must be an authority-derived frozen set")

    graph = StateGraph(WorkflowState)

    for step in normalized["steps"]:
        step_id = step["id"]

        async def run_step(state: WorkflowState, *, current=step) -> dict[str, Any]:
            previous = dict(state.get("steps") or {})
            step_name = current["id"]
            if step_name in previous:
                # A checkpointed run may be resumed. Never execute a finished
                # step again merely because the graph state was replayed.
                return {"steps": previous}

            if state.get("status") in ("failed", "waiting"):
                previous[step_name] = {"status": "blocked"}
                return {"steps": previous}

            required = current.get("depends_on", [])
            if any((previous.get(dep) or {}).get("status") not in
                   ("completed", "skipped") for dep in required):
                previous[step_name] = {"status": "blocked", "error_code": "dependency_unavailable"}
                return {"steps": previous, "status": "failed",
                        "error_code": "dependency_unavailable"}

            context = {"input": dict(state.get("input") or {}), "steps": previous}
            try:
                if "when" in current and not evaluate_condition(current["when"], context):
                    previous[step_name] = {"status": "skipped"}
                    return {"steps": previous}
            except WorkflowSpecError:
                previous[step_name] = {"status": "failed", "error_code": "invalid_condition"}
                return {"steps": previous, "status": "failed", "error_code": "invalid_condition"}

            if current["kind"] == "wait":
                # Persist the boundary and let Hatchet schedule the continuation.
                # Never sleep or keep an LLM worker alive for a delayed goal.
                previous[step_name] = {"status": "waiting"}
                return {"steps": previous, "status": "waiting",
                        "waiting_step": step_name}

            capability = current["capability_id"]
            if capability not in allowed_capabilities:
                previous[step_name] = {"status": "failed",
                                       "error_code": "capability_not_delegated"}
                return {"steps": previous, "status": "failed",
                        "error_code": "capability_not_delegated"}
            if int(state.get("action_count") or 0) >= MAX_READ_ACTIONS:
                previous[step_name] = {"status": "failed", "error_code": "action_budget"}
                return {"steps": previous, "status": "failed", "error_code": "action_budget"}

            try:
                arguments = render_value(current.get("arguments", {}), context)
                if not isinstance(arguments, dict):
                    raise ValueError("Non-object rendered arguments")
                if len(json.dumps(arguments, default=str).encode()) > 20_000:
                    raise ValueError("Arguments too large")
                response = await executor(capability, arguments,
                                          stable_request_id(run_id, step_name))
                if not isinstance(response, dict) or response.get("ok") is not True:
                    raise RuntimeError("Capability execution did not succeed")
                result = response.get("result")
                if not isinstance(result, dict) or len(
                    json.dumps(result, default=str).encode()
                ) > MAX_RESULT_BYTES:
                    raise ValueError("Capability result is invalid or too large")
                previous[step_name] = {"status": "completed", "result": result,
                                       "capability_id": capability}
                return {"steps": previous,
                        "action_count": int(state.get("action_count") or 0) + 1}
            except Exception:
                # Do not include exception text: an external tool may put
                # provider credentials, URLs, PII or prompt content in it.
                previous[step_name] = {"status": "failed", "error_code": "execution_failed"}
                if current.get("on_error") == "continue":
                    return {"steps": previous,
                            "action_count": int(state.get("action_count") or 0) + 1}
                return {"steps": previous, "status": "failed",
                        "error_code": "execution_failed",
                        "action_count": int(state.get("action_count") or 0) + 1}

        graph.add_node("step_" + step_id, run_step)

    async def finish(state: WorkflowState) -> dict[str, Any]:
        if state.get("status") in ("failed", "waiting"):
            return {}
        if any(x.get("status") == "failed"
               for x in (state.get("steps") or {}).values()):
            return {"status": "completed_with_errors"}
        return {"status": "completed"}

    graph.add_node("finish", finish)
    steps = normalized["steps"]
    graph.add_edge(START, "step_" + steps[0]["id"])
    for first, second in zip(steps, steps[1:]):
        graph.add_edge("step_" + first["id"], "step_" + second["id"])
    graph.add_edge("step_" + steps[-1]["id"], "finish")
    graph.add_edge("finish", END)
    return graph.compile(checkpointer=checkpointer)


async def run_readonly_workflow(
    spec: dict[str, Any],
    *,
    run_id: str,
    allowed_capabilities: frozenset[str],
    executor: ReadExecutor,
    input: dict[str, Any] | None = None,
    checkpointer=None,
):
    graph = compile_readonly_workflow(
        spec, run_id=run_id, allowed_capabilities=allowed_capabilities,
        executor=executor, checkpointer=checkpointer,
    )
    config = {"configurable": {"thread_id": stable_request_id(run_id, "thread")}}
    result = await graph.ainvoke(
        {"input": input or {}, "steps": {}, "status": "running",
         "action_count": 0}, config=config,
    )
    return {
        "run_id": run_id, "status": result.get("status", "incomplete"),
        "steps": result.get("steps", {}),
        "waiting_step": result.get("waiting_step"),
        "objective_verified": False,
        "action_count": result.get("action_count", 0),
    }
