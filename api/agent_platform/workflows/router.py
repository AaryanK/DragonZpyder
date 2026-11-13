"""DragonZpyder-owned, service-authenticated workflow control-plane contract.

This first slice centralizes the DAG language and cron/daily/weekly semantics.
Creation of *executing* cron jobs remains gated until a scheduled wakeup can
reacquire fresh user authorization. Preview never writes or starts anything.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .spec import (
    WorkflowSpecError, next_schedule_time, validate_schedule, validate_workflow_spec,
)

router = APIRouter(prefix="/internal/workflows", tags=["workflow-hub"])


def require_operly_service(authorization: str) -> None:
    if os.getenv("DRAGONZPYDER_WORKFLOW_HUB_ENABLED") != "1":
        raise HTTPException(503, "DragonZpyder workflow hub is not enabled")
    token = os.getenv("DRAGONZPYDER_OPERLY_AGENT_TOKEN", "")
    if len(token) < 40 or not authorization.startswith("Bearer ") or not hmac.compare_digest(
        token, authorization[7:]
    ):
        raise HTTPException(401, "Operly service authentication required")


class WorkflowPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schedule: dict | None = None
    spec: dict | None = None
    count: int = Field(default=5, ge=1, le=10)
    after: datetime | None = None


@router.post("/preview")
async def preview_workflow(
    request: WorkflowPreview, authorization: str = Header(default=""),
):
    require_operly_service(authorization)
    try:
        spec = validate_workflow_spec(request.spec) if request.spec is not None else None
        schedule = validate_schedule(request.schedule)
        if spec and len(spec["steps"]) > 30:
            raise WorkflowSpecError("Workflow exceeds current DragonZpyder step budget")
        cursor = (request.after or datetime.now(timezone.utc)).astimezone(
            timezone.utc
        ).replace(tzinfo=None) - timedelta(microseconds=1)
        occurrences = []
        if schedule:
            for _ in range(request.count):
                next_at = next_schedule_time(schedule, after=cursor)
                if next_at is None:
                    break
                occurrences.append(next_at.isoformat())
                cursor = next_at
    except (ValueError, TypeError, WorkflowSpecError) as exc:
        raise HTTPException(422, "Invalid workflow definition or schedule") from exc
    fingerprint = None
    if spec is not None:
        fingerprint = hashlib.sha256(
            json.dumps(spec, separators=(",", ":"), sort_keys=True).encode()
        ).hexdigest()
    return {
        "owner": "dragonzpyder",
        "source": "langgraph-hatchet",
        "schedule": schedule,
        "occurrences": occurrences,
        "step_count": len(spec["steps"]) if spec else None,
        "definition_sha256": fingerprint,
        "execution_started": False,
        "job_registered": False,
    }
