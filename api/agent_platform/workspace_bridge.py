"""Signed Workspace -> DragonZpyder Deep Agents bridge.

The caller is Operly's backend, never a browser or LLM. The short-lived
MCP bearer authenticates a particular session and workspace only inside the
MCP transport; its value is excluded from prompts and checkpoints.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from .personal_bridge import _authorized, execution_receipt_report, checkpoint_advanced_for_prompt

router = APIRouter()


class WorkspaceRun(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scope_kind: Literal["workspace"]
    user_id: str = Field(min_length=8, max_length=160)
    workspace_id: str = Field(min_length=8, max_length=160)
    session_id: str = Field(min_length=8, max_length=160)
    conversation_id: str = Field(min_length=8, max_length=120)
    prompt: str = Field(min_length=1, max_length=12000)
    mcp_access_token: str = Field(min_length=32, max_length=8192)
    approved_tool_names: list[str] = Field(min_length=1, max_length=20)


def workspace_thread(user_id: str, workspace_id: str, conversation_id: str) -> str:
    return hashlib.sha256(
        ("operly-workspace-v1\x00" + workspace_id + "\x00" + user_id +
         "\x00" + conversation_id).encode("utf-8")
    ).hexdigest()


@router.post("/internal/agents/operly/workspace/run", include_in_schema=False)
async def run_workspace(
    payload: WorkspaceRun, request: Request,
    authorization: str = Header(default=""),
    service_proof: str = Header(default="", alias="X-Operly-Agent-Service"),
):
    if not _authorized(authorization, service_proof, scope="workspace"):
        raise HTTPException(401, "Signed Workspace harness unavailable")
    runtime = getattr(request.app.state, "agent_runtime", None)
    checkpointer = getattr(runtime, "_checkpointer", None)
    if checkpointer is None:
        raise HTTPException(503, "Workspace checkpoint storage unavailable")
    approved = frozenset(payload.approved_tool_names)
    if len(approved) != len(payload.approved_tool_names):
        raise HTTPException(400, "Duplicate Workspace capability IDs")
    try:
        from .operly_mcp_client import load_authorized_operly_mcp_tools
        from .harness import build_frontier_agent
        from .runtime import model_client, summarize_agent_result
        tools = await asyncio.wait_for(load_authorized_operly_mcp_tools(
            url=os.getenv("DRAGONZPYDER_OPERLY_MCP_URL",
                          "https://operly.dragonzpyder.xyz/mcp"),
            access_token=payload.mcp_access_token,
            service_proof=service_proof,
            approved_tool_names=approved,
            max_tools=20,
        ), timeout=20)
        if not tools:
            raise ValueError("Authorized Workspace capability set is empty")
        # Never mix Personal goals, Personal token tools or unscoped tools
        # into a delegated Operly business Workspace.
        agent = build_frontier_agent(model_client(), checkpointer, delegated_tools=tools,
                                     product_surface="operly")
    except (ValueError, RuntimeError, asyncio.TimeoutError) as error:
        raise HTTPException(503, "Workspace MCP capability discovery unavailable") from error

    config = {"configurable": {
        "thread_id": workspace_thread(
            payload.user_id, payload.workspace_id, payload.conversation_id,
        ),
    }, "recursion_limit": 48}
    try:
        previous = await agent.aget_state(config)
    except Exception:
        previous = None
    try:
        result = await asyncio.wait_for(agent.ainvoke({
            "messages": [{"role": "user", "content": payload.prompt}],
        }, config=config), timeout=90)
        report = summarize_agent_result(result)
    except Exception as error:
        # Never fall back to a different agent on ambiguous network failures;
        # an upstream mutation could already have succeeded.
        raise HTTPException(503, "Workspace agent failed; reconcile before retry") from error
    try:
        checkpoint = await agent.aget_state(config)
        values = getattr(checkpoint, "values", None)
        checkpointed = (
            isinstance(values, dict)
            and checkpoint_advanced_for_prompt(previous, checkpoint, payload.prompt)
        )
    except Exception:
        checkpointed = False
    if not checkpointed:
        raise HTTPException(503, "Workspace checkpoint verification failed")
    return {
        "status": report["status"],
        "answer": str(report["answer"])[:16000],
        "successful_tools": [
            item for item in report.get("successful_tools", [])
            if isinstance(item, str) and item.startswith("operly_")
        ][:40],
        "execution_receipts": execution_receipt_report(report),
        "thread_checkpointed": True,
        "objective_verified": False,
    }
