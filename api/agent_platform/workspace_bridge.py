"""Operly Workspace -> DragonZpyder inference, without Operly's LLM harness.

Authenticated Operly is the Workspace membership/permission authority. This
service-only entrypoint runs the single DragonZpyder Deep Agents harness, with
NO business tools until a separate user/workspace-scoped MCP delegation exists.
Neither an ordinary DragonZpyder user nor an Operly browser can call it.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter()


class WorkspaceRun(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scope_kind: str = Field(pattern="^workspace$")
    user_id: UUID
    workspace_id: UUID
    conversation_id: UUID
    principal_id: str = Field(min_length=6, max_length=120)
    prompt: str = Field(min_length=1, max_length=12000)


def workspace_thread(payload: WorkspaceRun) -> str:
    return hashlib.sha256((
        "dragonzpyder-operly-workspace-v1\x00" + str(payload.workspace_id)
        + "\x00" + str(payload.user_id) + "\x00"
        + payload.principal_id + "\x00" + str(payload.conversation_id)
    ).encode("utf-8")).hexdigest()


def _authorized(authorization: str, proof: str) -> bool:
    token = os.getenv("DRAGONZPYDER_OPERLY_WORKSPACE_AGENT_TOKEN", "")
    seal = os.getenv("DRAGONZPYDER_OPERLY_WORKSPACE_SERVICE_SECRET", "")
    return (
        os.getenv("DRAGONZPYDER_WORKSPACE_DELEGATION_ENABLED") == "1"
        and os.getenv("DRAGONZPYDER_AGENTS_ENABLED") == "1"
        and os.getenv("DRAGONZPYDER_AGENT_USE_GATEWAY") == "1"
        and os.getenv("DRAGONZPYDER_AGENT_PRODUCTION_MODE") == "1"
        and len(token) >= 40 and len(seal) >= 40
        and token != seal
        and authorization.startswith("Bearer ")
        and hmac.compare_digest(authorization[7:], token)
        and hmac.compare_digest(proof, seal)
    )


@router.post("/internal/agents/operly/workspace/run")
async def run_workspace(
    payload: WorkspaceRun,
    request: Request,
    authorization: str = Header(default=""),
    proof: str = Header(default="", alias="X-Operly-Workspace-Service"),
):
    if not _authorized(authorization, proof):
        raise HTTPException(401, "Workspace service delegation disabled or unauthorized")
    # The principal is bound by a signed Operly backend request; never allow
    # a model to select workspace/user tools or reinterpret its permissions.
    if payload.principal_id != f"user:{payload.user_id}":
        raise HTTPException(403, "Unsupported Workspace principal")
    runtime = getattr(request.app.state, "agent_runtime", None)
    checkpointer = getattr(runtime, "_checkpointer", None)
    if checkpointer is None:
        raise HTTPException(503, "Agent checkpoint service unavailable")
    from .harness import build_frontier_agent
    from .runtime import model_client, summarize_agent_result
    from .personal_bridge import execution_receipt_report

    try:
        agent = build_frontier_agent(model_client(), checkpointer)
        config = {"configurable": {"thread_id": workspace_thread(payload)},
                  "recursion_limit": 48}
        result = await asyncio.wait_for(agent.ainvoke({
            "messages": [{"role": "user", "content": payload.prompt}],
        }, config=config), timeout=90)
        report = summarize_agent_result(result)
        persisted = await agent.aget_state(config)
        if not (persisted.values or {}).get("messages"):
            raise RuntimeError("Workspace checkpoint missing")
    except Exception:
        raise HTTPException(503, "DragonZpyder Workspace execution unavailable") from None

    return {
        "status": report["status"],
        "answer": report["answer"][:16000],
        "dispatch": "dragonzpyder_workspace_harness",
        "execution_receipts": execution_receipt_report(report),
        "thread_checkpointed": True,
        "objective_verified": False,
        # Business tool execution requires independently authorized Operly
        # OAuth/MCP grants and is deliberately not enabled by this route.
        "business_tools_enabled": False,
    }
