"""Signed Workspace -> DragonZpyder Deep Agents bridge.

The caller is Operly's backend, never a browser or LLM. The short-lived
MCP bearer authenticates a particular session and workspace only inside the
MCP transport; its value is excluded from prompts and checkpoints.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from uuid import uuid4
import os
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from .personal_bridge import _authorized, execution_receipt_report

router = APIRouter()
logger = logging.getLogger(__name__)
# Graph supersteps include middleware nodes, not just model calls. Keep the
# independent model/tool budgets and 90s deadline; allow their graph overhead.
WORKSPACE_RECURSION_LIMIT = 128


def workspace_turn_persisted(checkpoint, *, turn_id: str, prompt: str,
                             require_answer: bool = True) -> bool:
    """Prove this exact invocation, even on an empty or compacted thread."""
    values = getattr(checkpoint, "values", None)
    messages = values.get("messages") if isinstance(values, dict) else None
    if not isinstance(messages, list):
        return False
    matches = [i for i, message in enumerate(messages)
               if getattr(message, "id", None) == turn_id
               and getattr(message, "type", None) == "human"
               and getattr(message, "content", None) == prompt]
    if len(matches) != 1:
        return False
    tail = messages[matches[0] + 1:]
    if any(getattr(message, "type", None) == "human" for message in tail):
        return False
    return not require_answer or bool(
        tail and getattr(tail[-1], "type", None) == "ai"
        and not getattr(tail[-1], "tool_calls", None)
        and getattr(tail[-1], "content", None)
    )


def workspace_trace_evidence(checkpoint, *, turn_id: str, allowed_names: set[str]) -> dict:
    """Bounded current-turn diagnostics; never include input, arguments or results."""
    values = getattr(checkpoint, "values", None)
    messages = values.get("messages") if isinstance(values, dict) else None
    if not isinstance(messages, list):
        return {"current_turn_seen": False}
    positions = [i for i, m in enumerate(messages)
                 if getattr(m, "type", None) == "human" and getattr(m, "id", None) == turn_id]
    if len(positions) != 1:
        return {"current_turn_seen": False}
    tail = messages[positions[0] + 1:]
    if any(getattr(m, "type", None) == "human" for m in tail):
        return {"current_turn_seen": False}
    known = allowed_names | {"task", "write_todos", "ls", "read_file", "write_file",
                             "edit_file", "glob", "grep", "eval", "web_search"}
    def safe_name(value):
        return value if isinstance(value, str) and value in known else "other"
    attempts = []
    receipts = []
    model_messages = 0
    for m in tail:
        if getattr(m, "type", None) == "ai":
            model_messages += 1
            for call in getattr(m, "tool_calls", []) or []:
                if isinstance(call, dict) and len(attempts) < 40:
                    attempts.append(safe_name(call.get("name")))
        elif getattr(m, "type", None) == "tool" and len(receipts) < 40:
            receipts.append({"name": safe_name(getattr(m, "name", None)),
                             "status": "error" if getattr(m, "status", None) == "error" else "returned"})
    return {"current_turn_seen": True, "persisted_ai_messages": model_messages,
            "tool_attempts": attempts, "tool_returns": receipts}


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
        from .runtime import build_agent
        from .runtime import (model_client, summarize_agent_result,
                              controlled_termination_reason, summarize_checkpoint_evidence)
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
        from .adaptive_routing import routed_model
        model,route,route_middleware=routed_model(payload.prompt,model_factory=model_client,has_tools=True)
        agent = build_agent(model, checkpointer, delegated_tools=tools,
                                     product_surface="operly",
                                     **({"routing_middleware":route_middleware} if route_middleware else {}))
    except (ValueError, RuntimeError, asyncio.TimeoutError) as error:
        logger.warning("workspace_bridge_failed stage=discovery type=%s", type(error).__name__)
        raise HTTPException(503, "Workspace MCP capability discovery unavailable") from error

    config = {"configurable": {
        "thread_id": workspace_thread(
            payload.user_id, payload.workspace_id, payload.conversation_id,
        ),
    }, "recursion_limit": WORKSPACE_RECURSION_LIMIT}
    # A server-generated message ID survives persistence and distinguishes
    # repeated identical prompts from older turns. No pre-read is needed.
    turn_id = str(uuid4())
    allowed_names = {t.name for t in tools
                     if isinstance(getattr(t, "name", None), str)
                     and re.fullmatch(r"operly_[A-Za-z0-9_-]{1,79}", t.name)}
    logger.info("workspace_bridge_catalog turn=%s tools=%s", turn_id, sorted(allowed_names))
    try:
        result = await asyncio.wait_for(agent.ainvoke({
            "messages": [{"role": "user", "content": payload.prompt, "id": turn_id}],
        }, config=config), timeout=90)
        report = summarize_agent_result(result)
    except Exception as error:
        # No automatic retries or alternate agents after an ambiguous effect.
        reason = controlled_termination_reason(error)
        if reason is None:
            logger.warning("workspace_bridge_failed stage=execution type=%s", type(error).__name__)
            try:
                failed_checkpoint = await agent.aget_state(config)
                logger.info("workspace_bridge_trace turn=%s evidence=%s", turn_id,
                            workspace_trace_evidence(failed_checkpoint, turn_id=turn_id, allowed_names=allowed_names))
            except Exception:
                pass
            raise HTTPException(503, "Workspace agent failed; reconcile before retry") from error
        try:
            checkpoint = await agent.aget_state(config)
            if not workspace_turn_persisted(checkpoint, turn_id=turn_id,
                                            prompt=payload.prompt, require_answer=False):
                raise RuntimeError("Current workspace turn not persisted")
            report = summarize_checkpoint_evidence(checkpoint.values, termination_reason=reason)
        except Exception:
            logger.warning("workspace_bridge_failed stage=partial_checkpoint")
            raise HTTPException(503, "Workspace stopped; current checkpoint unavailable") from error
        logger.warning("workspace_bridge_incomplete reason=%s", reason)
    try:
        checkpoint = await agent.aget_state(config)
        checkpointed = workspace_turn_persisted(
            checkpoint, turn_id=turn_id, prompt=payload.prompt,
            require_answer=report["status"] == "completed",
        )
    except Exception:
        checkpointed = False
    if checkpointed:
        logger.info("workspace_bridge_trace turn=%s evidence=%s", turn_id,
                    workspace_trace_evidence(checkpoint, turn_id=turn_id, allowed_names=allowed_names))
    if not checkpointed:
        logger.warning("workspace_bridge_failed stage=checkpoint")
        raise HTTPException(503, "Workspace checkpoint verification failed")
    return {
        "status": report["status"],
        "answer": str(report["answer"])[:16000],
        "successful_tools": [
            item for item in report.get("successful_tools", [])
            if isinstance(item, str) and item.startswith("operly_")
        ][:40],
        "execution_receipts": execution_receipt_report(report),
        "termination_reason": report.get("termination_reason"),
        "thread_checkpointed": True,
        "objective_verified": False,
    }
