"""Service-only control plane for DragonZpyder-owned durable goal records.

This API registers and cancels durable *intent*. It cannot run scheduled
user tools yet. Hatchet execution must reacquire fresh user authorization
before work can transition beyond 'registered'.
"""
from __future__ import annotations

import hmac
import os

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from .goal_store import GoalConflict

router = APIRouter(prefix="/internal/goals", tags=["goal-hub"])


def _store(request: Request, authorization: str):
    if os.getenv("DRAGONZPYDER_GOAL_STORE_ENABLED") != "1":
        raise HTTPException(503, "Durable goal registry is not enabled")
    token = os.getenv("DRAGONZPYDER_OPERLY_AGENT_TOKEN", "")
    if (len(token) < 40 or not authorization.startswith("Bearer ") or
            not hmac.compare_digest(token, authorization[7:])):
        raise HTTPException(401, "Authenticated service caller required")
    store = getattr(request.app.state, "goal_store", None)
    if store is None:
        raise HTTPException(503, "Durable goal database unavailable")
    return store


class GoalOwner(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str = Field(pattern=r"^(personal|workspace)$")
    user_id: str = Field(min_length=1, max_length=120)
    workspace_id: str | None = Field(default=None, max_length=120)


class RegisterGoal(GoalOwner):
    request_id: str
    goal: str = Field(min_length=1, max_length=5000)
    schedule: dict | None = None


class TargetGoal(GoalOwner):
    goal_id: str


def _owner(payload):
    return {"source_app": "operly", "kind": payload.kind,
            "user_id": payload.user_id, "workspace_id": payload.workspace_id}


@router.post("/register")
async def register_goal(payload: RegisterGoal, request: Request,
                        authorization: str = Header(default="")):
    store = _store(request, authorization)
    try:
        return await store.register(
            **_owner(payload), request_id=payload.request_id,
            goal=payload.goal, schedule=payload.schedule,
        )
    except GoalConflict as exc:
        raise HTTPException(409, "Request ID conflicts with existing goal") from exc
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, "Invalid goal or schedule") from exc


@router.post("/get")
async def get_goal(payload: TargetGoal, request: Request,
                   authorization: str = Header(default="")):
    store = _store(request, authorization)
    try:
        return await store.get(**_owner(payload), goal_id=payload.goal_id)
    except LookupError as exc:
        raise HTTPException(404, "Goal not found in authorized scope") from exc
    except ValueError as exc:
        raise HTTPException(422, "Invalid goal reference") from exc


@router.post("/cancel")
async def cancel_goal(payload: TargetGoal, request: Request,
                      authorization: str = Header(default="")):
    store = _store(request, authorization)
    try:
        return await store.cancel(**_owner(payload), goal_id=payload.goal_id)
    except LookupError as exc:
        raise HTTPException(404, "Goal not found in authorized scope") from exc
    except ValueError as exc:
        raise HTTPException(422, "Invalid goal reference") from exc


@router.post("/runs")
async def get_goal_runs(payload: TargetGoal, request: Request,
                        authorization: str = Header(default="")):
    """Bounded, owner-scoped execution evidence; never return private goal text."""
    store = _store(request, authorization)
    try:
        runs = await store.list_runs(**_owner(payload), goal_id=payload.goal_id)
    except LookupError as exc:
        raise HTTPException(404, "Goal not found in authorized scope") from exc
    except ValueError as exc:
        raise HTTPException(422, "Invalid goal reference") from exc
    return {"runs": runs, "objective_verified": False}
