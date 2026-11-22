"""Internal-only, single-service experimental harness API.

Deliberately NOT a public user API or an Operly workspace authorization token.
Workspace-scoped execution must wait for signed user/tenant delegation.
"""
from __future__ import annotations

import hmac
import os
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

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


# Versioned operator pilot. This deliberately does not grant user or tenant
# authority, expose internal provider tokens, or start persistent workflows.
class AgentRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    prompt: str = Field(min_length=1, max_length=12000)


class AgentRunResponse(BaseModel):
    object: Literal["agent.run"] = "agent.run"
    id: str
    status: Literal["completed", "incomplete"]
    answer: str
    termination_reason: str | None = None
    successful_tools: list[str] = Field(default_factory=list)
    failed_tool_count: int = 0
    virtual_artifact_paths: list[str] = Field(default_factory=list)
    artifact_readback_paths: list[str] = Field(default_factory=list)
    objective_verified: Literal[False] = False


@router.post("/v1/agents/run", response_model=AgentRunResponse)
async def versioned_agent_run(
    payload: AgentRunRequest,
    request: Request,
    authorization: Annotated[str, Header()] = "",
):
    # Reuse the existing operator principal. Inference app keys, browser
    # cookies and arbitrary caller IDs are not agent execution authority.
    if os.getenv("DRAGONZPYDER_VERSIONED_AGENT_API_ENABLED") != "1":
        raise HTTPException(404, "Versioned agent API disabled")
    service_id = authenticated_service(authorization)
    if os.getenv("DRAGONZPYDER_AGENTS_ENABLED") != "1":
        raise HTTPException(503, "Agent runtime disabled")
    # Pilot only: require the existing gateway's upstream hard-cap check
    # on every paid request. Do not silently allow direct provider mode.
    if (
        os.getenv("DRAGONZPYDER_AGENT_USE_GATEWAY") != "1"
        or os.getenv("DRAGONZPYDER_AGENT_TOOL_CALLS_ENABLED") != "1"
        or os.getenv("DRAGONZPYDER_AGENT_PAID_TEST_MAX_KEY_LIMIT_USD") != "0.50"
    ):
        raise HTTPException(503, "Metered pilot gateway required")
    runtime = getattr(request.app.state, "agent_runtime", None)
    if runtime is None:
        raise HTTPException(503, "Agent runtime unavailable")
    # Each request gets a fresh checkpoint namespace, avoiding caller-
    # controlled resume or concurrent writes to an existing thread.
    run_id = uuid4().hex
    try:
        report = await runtime.run_report(
            service_id=service_id,
            thread_id="api-v1-" + run_id,
            prompt=payload.prompt,
            recover_partial_on_failure=True,
        )
        return AgentRunResponse(
            id=run_id,
            status=report["status"],
            answer=report["answer"],
            termination_reason=report.get("termination_reason"),
            successful_tools=report.get("successful_tools", []),
            failed_tool_count=report.get("failed_tool_count", 0),
            virtual_artifact_paths=report.get("virtual_artifact_paths", []),
            artifact_readback_paths=report.get("artifact_readback_paths", []),
        )
    except Exception:
        # Do not return upstream exceptions, keys or raw internal traces.
        raise HTTPException(502, "Agent execution did not return a report") from None
