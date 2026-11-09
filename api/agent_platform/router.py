"""Internal-only, single-service experimental harness API.

Deliberately NOT a public user API or an Operly workspace authorization token.
Workspace-scoped execution must wait for signed user/tenant delegation.
"""
from __future__ import annotations

import hmac
import os
from typing import Annotated
import hashlib

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter()


class OperlyDelegatedPrompt(BaseModel):
    """Operly-owned human scope, never sent directly from a browser."""

    model_config = {"extra": "forbid"}
    thread_id: str = Field(pattern=r"^[a-zA-Z0-9_.-]{1,80}$")
    prompt: str = Field(min_length=1, max_length=12000)
    scope_kind: str = Field(pattern=r"^(workspace|personal)$")
    user_id: str = Field(min_length=1, max_length=120)
    workspace_id: str | None = Field(default=None, max_length=120)
    lease_token: str = Field(min_length=20, max_length=6000)


@router.post("/internal/agents/operly/run")
async def run_operly_agent(
    payload: OperlyDelegatedPrompt,
    request: Request,
    authorization: Annotated[str, Header()] = "",
):
    """First opt-in migration cut: LangGraph owns reasoning; Operly owns tools.

    Only an authenticated Operly backend can request a run. The enclosed lease
    is not trusted by DragonZpyder; the Operly broker validates it per tool.
    """
    enabled = all(os.getenv(key) == "1" for key in (
        "DRAGONZPYDER_AGENTS_ENABLED",
        "DRAGONZPYDER_AGENT_OPERLY_READONLY_ENABLED",
        "DRAGONZPYDER_AGENT_USE_GATEWAY",
        "DRAGONZPYDER_AGENT_PRODUCTION_MODE",
        "DRAGONZPYDER_AGENT_HARNESS_V2",
    ))
    if not enabled:
        raise HTTPException(503, "Delegated agent runtime is disabled")
    secret = os.getenv("DRAGONZPYDER_OPERLY_AGENT_TOKEN", "")
    if (len(secret) < 40 or not authorization.startswith("Bearer ") or
            not hmac.compare_digest(secret, authorization[7:])):
        raise HTTPException(401, "Operly service authentication required")
    if (payload.scope_kind == "personal" and payload.workspace_id is not None) or (
        payload.scope_kind == "workspace" and not payload.workspace_id
    ):
        raise HTTPException(400, "Invalid delegated scope")
    agent = getattr(request.app.state, "agent_runtime", None)
    if agent is None:
        raise HTTPException(503, "Agent runtime unavailable")
    # The service-token caller alone supplies this scope; no user-editable
    # cookies, provider keys or workspace identifiers are accepted elsewhere.
    seed = "|".join((payload.scope_kind, payload.user_id, payload.workspace_id or ""))
    scope_key = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]
    from .operly_broker import readonly_tools, OperlyBrokerUnavailable
    from .runtime import AgentPipelineError
    try:
        tools = readonly_tools(payload.lease_token)
        report = await agent.run_report(
            service_id="operly-" + scope_key,
            thread_id=payload.thread_id,
            prompt=payload.prompt,
            recover_partial_on_failure=True,
            external_tools=tools,
        )
    except OperlyBrokerUnavailable as exc:
        raise HTTPException(503, "Operly tool broker unavailable") from exc
    except (AgentPipelineError, RuntimeError) as exc:
        raise HTTPException(502, "DragonZpyder harness run failed") from exc
    return {
        "message": report.get("answer", ""),
        "status": report.get("status", "incomplete"),
        "successful_tools": report.get("successful_tools", [])[:40],
        "objective_verified": False,
        "termination_reason": report.get("termination_reason"),
    }


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
