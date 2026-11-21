"""Operly Personal's signed-session → DragonZpyder Deep Agents entrypoint.

A private service-authenticated route only. Browser cookies and raw OAuth
provider credentials are never used here. Operly is authoritative for the
actual user, permitted capabilities, session lifecycle and revocation.
LangGraph checkpoints use a user+conversation-isolated PostgreSQL thread.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter()


class OperlyPersonalRun(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scope_kind: Literal["personal"]
    user_id: str = Field(min_length=8, max_length=80)
    session_id: str = Field(min_length=8, max_length=80)
    conversation_id: str = Field(min_length=8, max_length=120)
    prompt: str = Field(min_length=1, max_length=12000)
    mcp_access_token: str = Field(min_length=32, max_length=8192)
    approved_tool_names: list[str] = Field(min_length=1, max_length=20)


def _authorized(authorization: str, proof: str) -> bool:
    agent_secret = os.getenv("DRAGONZPYDER_OPERLY_PERSONAL_AGENT_TOKEN", "")
    mcp_secret = os.getenv("DRAGONZPYDER_OPERLY_MCP_SERVICE_SECRET", "")
    return (all(os.getenv(k) == "1" for k in (
                "DRAGONZPYDER_PERSONAL_MCP_HARNESS_ENABLED",
                "DRAGONZPYDER_AGENTS_ENABLED",
                "DRAGONZPYDER_AGENT_HARNESS_V2",
                "DRAGONZPYDER_OPERLY_TOOLS_ENABLED",
                "DRAGONZPYDER_OPERLY_MCP_ENABLED",
                "DRAGONZPYDER_AGENT_USE_GATEWAY",
                "DRAGONZPYDER_AGENT_PRODUCTION_MODE",
            ))
            and len(agent_secret) >= 40 and len(mcp_secret) >= 40
            and authorization.startswith("Bearer ")
            and hmac.compare_digest(authorization[7:], agent_secret)
            and hmac.compare_digest(proof, mcp_secret))


def personal_thread(user_id: str, conversation_id: str) -> str:
    # Never use the untrusted conversation ID on its own as a checkpoint key.
    # This prevents different users from landing in the same persisted thread.
    return hashlib.sha256(
        ("operly-personal-v1\x00" + user_id + "\x00" + conversation_id).encode()
    ).hexdigest()


@router.post("/internal/agents/operly/personal/run")
async def operly_personal_run(
    payload: OperlyPersonalRun,
    request: Request,
    authorization: str = Header(default=""),
    service_proof: str = Header(default="", alias="X-Operly-Agent-Service"),
):
    if not _authorized(authorization, service_proof):
        raise HTTPException(401, "First-party Personal harness is disabled or unauthorized")
    runtime = getattr(request.app.state, "agent_runtime", None)
    checkpointer = getattr(runtime, "_checkpointer", None)
    if checkpointer is None:
        raise HTTPException(503, "Persistent agent checkpoint is unavailable")

    from .harness import build_frontier_agent
    from .operly_mcp_client import load_authorized_operly_mcp_tools
    from .runtime import (
        controlled_termination_reason,
        model_client,
        summarize_agent_result,
        summarize_checkpoint_evidence,
    )
    approved = frozenset(payload.approved_tool_names)
    if len(approved) != len(payload.approved_tool_names):
        raise HTTPException(400, "Duplicate authorized capability IDs")
    try:
        tools = await asyncio.wait_for(load_authorized_operly_mcp_tools(
            url=os.getenv(
                "DRAGONZPYDER_OPERLY_MCP_URL",
                "https://operly.dragonzpyder.xyz/mcp",
            ),
            access_token=payload.mcp_access_token,
            service_proof=service_proof,
            approved_tool_names=approved,
            max_tools=20,
        ), timeout=20)
        agent = build_frontier_agent(
            model_client(), checkpointer, delegated_tools=tools,
        )
    except (ValueError, RuntimeError, asyncio.TimeoutError) as error:
        # No model query or credentials are included in HTTP error payload.
        raise HTTPException(503, "Authorized Personal MCP tools unavailable") from error
    config = {
        "configurable": {
            "thread_id": personal_thread(payload.user_id, payload.conversation_id),
        },
        "recursion_limit": 48,
    }
    try:
        result = await asyncio.wait_for(
            agent.ainvoke({
                "messages": [{"role": "user", "content": payload.prompt}],
            }, config=config),
            timeout=90,
        )
    except Exception as error:
        reason = controlled_termination_reason(error)
        if not reason:
            raise HTTPException(503, "Personal agent execution failed") from error
        try:
            checkpoint = await agent.aget_state(config)
            state = checkpoint.values
        except Exception:
            state = None
        report = summarize_checkpoint_evidence(state, termination_reason=reason)
    else:
        report = summarize_agent_result(result)
    # Verify actual persisted LangGraph checkpoint readback before claiming
    # that a future Hatchet wake can resume this user's conversation.
    try:
        readback = await agent.aget_state(config)
        saved_messages = readback.values.get("messages", [])
        checkpointed = isinstance(saved_messages, list) and len(saved_messages) > 0
    except Exception:
        checkpointed = False
    if not checkpointed:
        raise HTTPException(503, "Personal agent checkpoint verification failed")
    return {
        "status": report["status"],
        "answer": report["answer"][:16000],
        "successful_tools": [
            name for name in report.get("successful_tools", [])
            if isinstance(name, str) and name.startswith("operly_")
        ][:40],
        "termination_reason": report.get("termination_reason"),
        "thread_checkpointed": checkpointed,
        "objective_verified": False,
    }
