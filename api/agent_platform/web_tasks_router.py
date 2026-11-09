"""Private, service-authenticated live harness tasks for DragonZpyder Web.

Never accept browser cookies or a user-provided service authorization here.
DragonZpyder Web verifies the Operly Personal session and sends the resolved
owner identity with a dedicated backend-only token.
"""
from __future__ import annotations

import hmac
import os
from typing import Annotated, Literal

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(prefix="/internal/web-tasks", tags=["private-task-activity"])


class Owner(BaseModel):
    model_config = ConfigDict(extra="forbid")
    owner: str = Field(min_length=3, max_length=250)


class Submit(Owner):
    request_id: str
    kind: Literal["probe", "agent"]
    goal: str = Field(min_length=1, max_length=5000)


class Identify(Owner):
    task_id: str


class AdminIdentify(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_id: str


def store_for(request: Request, authorization: str):
    if os.getenv("DRAGONZPYDER_WEB_TASKS_ENABLED") != "1":
        raise HTTPException(503, "Web tasks are not available")
    expected = os.getenv("DRAGONZPYDER_WEB_TASK_SERVICE_TOKEN", "")
    if not (len(expected) >= 40 and authorization.startswith("Bearer ")
            and hmac.compare_digest(authorization[7:], expected)):
        raise HTTPException(401, "Web backend authentication required")
    store = getattr(request.app.state, "activity_store", None)
    if store is None:
        raise HTTPException(503, "Task store is unavailable")
    return store


@router.post("/submit")
async def submit(payload: Submit, request: Request,
                 authorization: str = Header(default="")):
    store = store_for(request, authorization)
    if payload.kind == "agent":
        # An arbitrary browser task must not start model billing unless the
        # gateway transactionally enforces a per-job ceiling of $0.05.
        from main import parent_budget
        if (os.getenv("DRAGONZPYDER_WEB_TASKS_PAID_ENABLED") != "1"
                or os.getenv("DRAGONZPYDER_AGENT_USE_GATEWAY") != "1"
                or not parent_budget.active):
            raise HTTPException(503, "Budgeted agent tasks are disabled")
    try:
        task, created = await store.create(
            owner=payload.owner, request_id=payload.request_id,
            kind=payload.kind, prompt=payload.goal,
        )
    except ValueError as exc:
        raise HTTPException(409, "Invalid or duplicate task request") from exc
    if not created:
        return {**task, "new": False}

    from .web_task_worker import WebTaskInput
    try:
        if payload.kind == "agent":
            from main import parent_budget
            await parent_budget.create(
                job_id=task["task_id"], ceiling_usd="0.05"
            )
        from hatchet_sdk import Hatchet
        from .web_task_worker import make_web_task
        task_ref = await make_web_task(Hatchet()).aio_run_no_wait(
            WebTaskInput(task_id=task["task_id"])
        )
        await store.append(task["task_id"], "queued", "Dispatched to Hatchet worker")
    except Exception as exc:
        await store.dispatch_failed(task["task_id"])
        # Do not expose private Hatchet host, API keys or provider traceback.
        raise HTTPException(503, "Hatchet task dispatch unavailable") from exc
    return {**task, "new": True}


@router.post("/list")
async def list_user(payload: Owner, request: Request,
                    authorization: str = Header(default="")):
    store = store_for(request, authorization)
    return {"tasks": await store.list(owner=payload.owner)}


@router.post("/detail")
async def detail(payload: Identify, request: Request,
                 authorization: str = Header(default="")):
    store = store_for(request, authorization)
    try:
        return await store.get(owner=payload.owner, task_id=payload.task_id)
    except (LookupError, ValueError) as exc:
        raise HTTPException(404, "Task not found") from exc


@router.post("/cancel")
async def cancel(payload: Identify, request: Request,
                 authorization: str = Header(default="")):
    store = store_for(request, authorization)
    try:
        return await store.cancel(owner=payload.owner, task_id=payload.task_id)
    except (LookupError, ValueError) as exc:
        raise HTTPException(404, "Task not found") from exc


@router.post("/admin/list")
async def admin_list(request: Request, authorization: str = Header(default="")):
    store = store_for(request, authorization)
    # Admin verification occurs in the web app; private service token is
    # NEVER held by a browser. Only sanitized operational data is returned.
    return {"tasks": await store.list(admin=True)}


@router.post("/admin/detail")
async def admin_detail(payload: AdminIdentify, request: Request,
                       authorization: str = Header(default="")):
    store = store_for(request, authorization)
    try:
        return await store.get(owner=None, task_id=payload.task_id, admin=True)
    except (LookupError, ValueError) as exc:
        raise HTTPException(404, "Task not found") from exc
