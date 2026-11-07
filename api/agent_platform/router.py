"""Internal-only, single-service experimental harness API.

Deliberately NOT a public user API or an Operly workspace authorization token.
Workspace-scoped execution must wait for signed user/tenant delegation.
"""
from __future__ import annotations

import hmac
import os
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter()


class AgentPrompt(BaseModel):
    thread_id: str = Field(pattern=r"^[a-zA-Z0-9_.-]{1,80}$")
    prompt: str = Field(min_length=1, max_length=12000)


def authenticated_service(authorization: str) -> str:
    token = os.getenv("DRAGONZPYDER_AGENT_SERVICE_TOKEN", "")
    if len(token) < 40 or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Unauthorized")
    if not hmac.compare_digest(token, authorization[7:]):
        raise HTTPException(401, "Unauthorized")
    # The token grants exactly one service principal, not delegated user access.
    return "agent-smoke"


@router.post("/internal/agents/run")
async def run_agent(
    payload: AgentPrompt,
    request: Request,
    authorization: Annotated[str, Header()] = "",
):
    if os.getenv("DRAGONZPYDER_AGENTS_ENABLED") != "1":
        raise HTTPException(404, "Agent runtime disabled")
    service_id = authenticated_service(authorization)
    runtime = getattr(request.app.state, "agent_runtime", None)
    if runtime is None:
        raise HTTPException(503, "Agent runtime unavailable")
    try:
        answer = await runtime.run(
            service_id=service_id,
            thread_id=payload.thread_id,
            prompt=payload.prompt,
        )
    except ValueError:
        raise HTTPException(400, "Invalid agent request") from None
    return {"thread_id": payload.thread_id, "answer": answer}
