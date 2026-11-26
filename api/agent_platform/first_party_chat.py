"""First-party Personal Agent HTTP surface.

Web, Android (via Web), and future native clients enter DragonZpyder before
any optional MCP integration. No Operly session, service proof, or user-chosen
principal is accepted. This migration surface is OFF until first-party
identity, checkpoint storage, and conversation schema are deployed.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

import asyncpg
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from identity.http_bridge import _identity_db, _issuer
from identity.sessions import SessionDenied, resolve_browser_session

router = APIRouter(prefix="/v2/personal", tags=["first-party-personal"])


class ChatInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=12000)
    attachment_ids: list[UUID] = Field(default_factory=list, max_length=5)
    allow_computer: bool = Field(default=False, strict=True)
    conversation_id: UUID | None = None
    request_id: UUID | None = None
    # Aliases must belong to the authenticated user and are rechecked at use.
    mcp_connection_ids: list[str] = Field(default_factory=list, max_length=10)


def _enabled() -> None:
    if (os.getenv("DRAGONZPYDER_FIRST_PARTY_CHAT_ENABLED") != "1"
            or os.getenv("DRAGONZPYDER_IDENTITY_HTTP_ENABLED") != "1"):
        raise HTTPException(404, "Not found")
    if os.getenv("DRAGONZPYDER_AGENTS_ENABLED") != "1":
        raise HTTPException(503, "DragonZpyder agent runtime unavailable")


async def _owner(request: Request, *, changing: bool) -> str:
    _enabled()
    # Origin is checked by the first-party issuer and by the web's restricted
    # same-origin reverse proxy. A browser cannot choose its execution user.
    if changing and request.headers.get("origin") != _issuer():
        raise HTTPException(403, "Origin rejected")
    secret = request.cookies.get("__Host-dz_identity", "")
    csrf = request.headers.get("x-dz-csrf", "") if changing else None
    try:
        async with _identity_db() as conn:
            return await resolve_browser_session(
                conn, secret=secret, csrf=csrf, require_csrf=changing,
            )
    except SessionDenied:
        raise HTTPException(401, "Active DragonZpyder session required") from None


@asynccontextmanager
async def _conversation_db():
    dsn = os.getenv("DRAGONZPYDER_AGENT_DATABASE_URL", "")
    if not dsn.startswith(("postgres://", "postgresql://")):
        raise HTTPException(503, "Conversation storage unavailable")
    try:
        conn = await asyncpg.connect(dsn=dsn, timeout=5, command_timeout=120)
    except (OSError, asyncpg.PostgresError, TimeoutError):
        raise HTTPException(503, "Conversation storage unavailable") from None
    try:
        yield conn
    finally:
        await conn.close()


async def _require_conversation(db, *, user: str, conversation_id: UUID):
    row = await db.fetchrow(
        "SELECT id FROM dz_first_party_conversations WHERE id=$1 AND owner_id=$2",
        conversation_id, user,
    )
    if row is None:
        # Deliberately indistinguishable: unknown and other-user IDs.
        raise HTTPException(404, "Conversation not found")


@router.get("/status")
async def status():
    """Non-authority-bearing rollout signal for the web/Android shells."""
    enabled = (os.getenv("DRAGONZPYDER_FIRST_PARTY_CHAT_ENABLED") == "1"
               and os.getenv("DRAGONZPYDER_IDENTITY_HTTP_ENABLED") == "1"
               and os.getenv("DRAGONZPYDER_AGENTS_ENABLED") == "1")
    return {"native_chat_enabled": enabled,
            "artifacts_enabled": enabled and os.getenv("DRAGONZPYDER_AGENT_ARTIFACTS_ENABLED") == "1" and bool(os.getenv("DRAGONZPYDER_ARTIFACT_KEY_B64")),
            "computer_enabled": enabled and all(os.getenv(flag) == "1" for flag in (
                "DRAGONZPYDER_FIRST_PARTY_COMPUTER_ENABLED", "DRAGONZPYDER_AGENT_ARTIFACTS_ENABLED",
                "DRAGONZPYDER_FIRST_PARTY_REQUEST_LEDGER_ENABLED", "DRAGONZPYDER_FIRST_PARTY_STREAM_ENABLED"))
                and all(bool(os.getenv(key)) for key in ("DRAGONZPYDER_COMPUTER_MAX_SESSION_USD",
                "DRAGONZPYDER_COMPUTER_OWNER_DAILY_USD","DRAGONZPYDER_COMPUTER_GLOBAL_DAILY_USD",
                "DRAGONZPYDER_COMPUTER_RUNNER_URL","DRAGONZPYDER_COMPUTER_RUNNER_TOKEN",
                "DRAGONZPYDER_COMPUTER_RUNNER_SIGNING_KEY","DRAGONZPYDER_ARTIFACT_KEY_B64")),
            "voice_enabled": enabled and os.getenv("DRAGONZPYDER_NATIVE_VOICE_ENABLED") == "1" and bool(os.getenv("DRAGONZPYDER_NATIVE_VOICE_API_KEY")),
            "request_ledger_enabled": enabled and os.getenv("DRAGONZPYDER_FIRST_PARTY_REQUEST_LEDGER_ENABLED") == "1",
            "agent_stream_enabled": enabled and os.getenv("DRAGONZPYDER_FIRST_PARTY_REQUEST_LEDGER_ENABLED") == "1" and os.getenv("DRAGONZPYDER_FIRST_PARTY_STREAM_ENABLED") == "1",
            "goal_management_enabled": enabled and os.getenv("DRAGONZPYDER_FIRST_PARTY_GOAL_MANAGEMENT_ENABLED") == "1",
            "web_cutover_enabled": (enabled and
                os.getenv("DRAGONZPYDER_FIRST_PARTY_WEB_CUTOVER_ENABLED") == "1")}


@router.get("/session")
async def session(request: Request):
    await _owner(request, changing=False)
    return {"authenticated": True, "runtime": "dragonzpyder"}


def _goals_enabled():
    if os.getenv("DRAGONZPYDER_FIRST_PARTY_GOAL_MANAGEMENT_ENABLED") != "1":
        raise HTTPException(503, "First-party goal management unavailable")


@router.get("/goals")
async def goals(request: Request):
    user = await _owner(request, changing=False)
    _goals_enabled()
    async with _conversation_db() as db:
        rows = await db.fetch(
            """SELECT goal_id, conversation_id, state, next_sequence, total_wakes,
                      blocked_reason, updated_at
               FROM dz_personal_mcp_goals WHERE user_id=$1
               ORDER BY updated_at DESC LIMIT 100""", user)
    return {"goals": [
        {"goal_id": row["goal_id"], "conversation_id": row["conversation_id"],
         "state": row["state"], "completed_wakes": row["next_sequence"],
         "total_wakes": row["total_wakes"],
         "blocked_reason": row["blocked_reason"] if row["state"] == "blocked" else None,
         "updated_at": row["updated_at"].isoformat()} for row in rows]}


@router.get("/goals/{goal_id}")
async def goal_detail(goal_id: UUID, request: Request):
    user = await _owner(request, changing=False)
    _goals_enabled()
    async with _conversation_db() as db:
        row = await db.fetchrow(
            """SELECT goal_id, state, next_sequence, total_wakes, blocked_reason
               FROM dz_personal_mcp_goals WHERE user_id=$1 AND goal_id=$2""",
            user, str(goal_id))
        if row is None:
            raise HTTPException(404, "Goal not found")
        receipts = await db.fetch(
            """SELECT r.sequence, r.status, r.tool_names, r.created_at
               FROM dz_personal_mcp_receipts r JOIN dz_personal_mcp_goals g
               ON r.goal_id=g.goal_id WHERE g.user_id=$1 AND g.goal_id=$2
               ORDER BY r.sequence""", user, str(goal_id))
    return {"goal_id": str(goal_id), "state": row["state"],
            "completed_wakes": row["next_sequence"], "total_wakes": row["total_wakes"],
            "blocked_reason": row["blocked_reason"] if row["state"] == "blocked" else None,
            "receipts": [{"sequence": x["sequence"], "status": x["status"],
                          "tool_names": json.loads(x["tool_names"]) if isinstance(x["tool_names"], str) else x["tool_names"],
                          "at": x["created_at"].isoformat()} for x in receipts]}


@router.post("/goals/{goal_id}/cancel")
async def cancel_goal(goal_id: UUID, request: Request):
    user = await _owner(request, changing=True)
    _goals_enabled()
    async with _conversation_db() as db:
        row = await db.fetchrow(
            """UPDATE dz_personal_mcp_goals SET state='cancelled', updated_at=now()
               WHERE user_id=$1 AND goal_id=$2 AND state IN ('preparing','active')
               RETURNING state""", user, str(goal_id))
        if row is None:
            existing = await db.fetchrow(
                "SELECT state FROM dz_personal_mcp_goals WHERE user_id=$1 AND goal_id=$2",
                user, str(goal_id))
            if existing is None:
                raise HTTPException(404, "Goal not found")
            if existing["state"] == "cancelled":
                return {"goal_id": str(goal_id), "state": "cancelled"}
            raise HTTPException(409, "Goal is not cancellable in its current state")
    return {"goal_id": str(goal_id), "state": "cancelled"}


@router.get("/conversations")
async def conversations(request: Request):
    user = await _owner(request, changing=False)
    async with _conversation_db() as db:
        rows = await db.fetch(
            """SELECT id, title, updated_at FROM dz_first_party_conversations
               WHERE owner_id=$1 ORDER BY updated_at DESC LIMIT 100""", user,
        )
    return {"conversations": [
        {"id": str(row["id"]), "title": row["title"],
         "updated_at": row["updated_at"].isoformat()} for row in rows
    ]}


@router.get("/conversations/{conversation_id}/messages")
async def messages(conversation_id: UUID, request: Request):
    user = await _owner(request, changing=False)
    async with _conversation_db() as db:
        await _require_conversation(db, user=user, conversation_id=conversation_id)
    runtime = getattr(request.app.state, "agent_runtime", None)
    if runtime is None or runtime._checkpointer is None:
        raise HTTPException(503, "Agent checkpoints unavailable")
    from .personal_bridge import personal_thread
    from .harness import build_frontier_agent
    from .runtime import model_client
    agent = build_frontier_agent(model_client(), runtime._checkpointer)
    config = {"configurable": {"thread_id": personal_thread(user, str(conversation_id))}}
    try:
        state = await agent.aget_state(config)
    except Exception:
        raise HTTPException(503, "Conversation checkpoint unavailable") from None
    rows = []
    for item in (state.values or {}).get("messages", [])[-200:]:
        role = getattr(item, "type", None)
        content = getattr(item, "content", None)
        if role == "human":
            role = "user"
        elif role == "ai":
            role = "assistant"
        else:
            continue
        if isinstance(content, str):
            rows.append({"role": role, "content": content[:16000]})
    return {"messages": rows}


def _fingerprint(payload: ChatInput) -> str:
    exclude = {"request_id"}
    if not payload.attachment_ids:
        exclude.add("attachment_ids")  # preserve existing ledger fingerprints
    if not payload.allow_computer:
        exclude.add("allow_computer")
    canonical = json.dumps(payload.model_dump(mode="json", exclude=exclude),
                           sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _ledger_response(row, fingerprint: str | None = None):
    if fingerprint is not None and row["fingerprint"] != fingerprint:
        raise HTTPException(409, "Request ID is already bound to different input")
    result = {"request_id": str(row["request_id"]),
              "conversation_id": str(row["conversation_id"]), "status": row["status"],
              "cancel_requested": bool(row.get("cancel_requested", False))}
    if row["status"] == "completed":
        value = row["response"]
        result["response"] = json.loads(value) if isinstance(value, str) else value
    return result


@router.get("/requests/{request_id}")
async def request_status(request_id: UUID, request: Request):
    user = await _owner(request, changing=False)
    if os.getenv("DRAGONZPYDER_FIRST_PARTY_REQUEST_LEDGER_ENABLED") != "1":
        raise HTTPException(503, "Request ledger is not enabled")
    async with _conversation_db() as db:
        row = await db.fetchrow(
            """SELECT request_id, fingerprint, conversation_id, status, response, cancel_requested
               FROM dz_first_party_chat_requests WHERE owner_id=$1 AND request_id=$2""",
            user, request_id)
    if row is None:
        raise HTTPException(404, "Request not found")
    return _ledger_response(row)


@router.post("/requests/{request_id}/cancel")
async def cancel_request(request_id: UUID, request: Request):
    user = await _owner(request, changing=True)
    if os.getenv("DRAGONZPYDER_FIRST_PARTY_REQUEST_LEDGER_ENABLED") != "1":
        raise HTTPException(503, "Request ledger is not enabled")
    async with _conversation_db() as db:
        row = await db.fetchrow(
            """UPDATE dz_first_party_chat_requests SET cancel_requested=true, updated_at=now()
               WHERE owner_id=$1 AND request_id=$2 AND status='accepted'
               RETURNING request_id, fingerprint, conversation_id, status, response, cancel_requested""",
            user, request_id)
        if row is None:
            row = await db.fetchrow(
                """SELECT request_id, fingerprint, conversation_id, status, response, cancel_requested
                   FROM dz_first_party_chat_requests WHERE owner_id=$1 AND request_id=$2""",
                user, request_id)
    if row is None:
        raise HTTPException(404, "Request not found")
    return _ledger_response(row)


@router.post("/chat")
async def chat(payload: ChatInput, request: Request):
    user = await _owner(request, changing=True)
    return await _chat_owned(payload, request, user)


@router.post("/chat/stream")
async def chat_stream(payload: ChatInput, request: Request):
    user = await _owner(request, changing=True)
    if (os.getenv("DRAGONZPYDER_FIRST_PARTY_STREAM_ENABLED") != "1"
            or os.getenv("DRAGONZPYDER_FIRST_PARTY_REQUEST_LEDGER_ENABLED") != "1"):
        raise HTTPException(503, "Agent streaming unavailable")
    if payload.request_id is None or not payload.message.strip():
        raise HTTPException(422, "Streaming requires a request ID and message")
    queue = asyncio.Queue(maxsize=256)
    def emit(event):
        # A disconnected or slow consumer must never block agent execution.
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            pass
    def encode(event):
        return "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"
    async def events():
        task = asyncio.create_task(_chat_owned(payload, request, user, emit))
        tasks = getattr(request.app.state, "native_stream_tasks", None)
        if tasks is None:
            tasks = set()
            request.app.state.native_stream_tasks = tasks
        tasks.add(task)
        def cleanup(done):
            tasks.discard(done)
            if not done.cancelled():
                done.exception()
        task.add_done_callback(cleanup)
        yield encode({"type":"phase","message":"Request received"})
        while not task.done():
            try:
                event = await asyncio.wait_for(queue.get(), timeout=2)
                yield encode(event)
            except asyncio.TimeoutError:
                yield ": heartbeat\n\n"
        while not queue.empty():
            yield encode(queue.get_nowait())
        try:
            result = task.result()
        except HTTPException as error:
            detail = error.detail
            message = detail.get("message","Request failed") if isinstance(detail,dict) else str(detail)
            yield encode({"type":"error","message":message,"status":error.status_code})
        except (Exception, asyncio.CancelledError):
            yield encode({"type":"error","message":"Request outcome unconfirmed; check request status"})
        else:
            yield encode({"type":"done","response":result})
    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control":"no-store","X-Accel-Buffering":"no"})


async def _chat_owned(payload: ChatInput, request: Request, user: str, emit=None):
    if not payload.message.strip():
        raise HTTPException(422, "Message cannot be blank")
    if payload.attachment_ids:
        if len(set(payload.attachment_ids)) != len(payload.attachment_ids):
            raise HTTPException(422, "Duplicate attachment IDs")
        from .artifacts import describe
        async with _conversation_db() as db:
            await describe(db,owner=user,ids=payload.attachment_ids)
    if payload.allow_computer:
        if os.getenv("DRAGONZPYDER_FIRST_PARTY_COMPUTER_ENABLED") != "1":
            raise HTTPException(503,"Isolated computer execution unavailable")
        if payload.request_id is None:
            raise HTTPException(422,"Computer execution requires durable request identity")
    # Old clients remain compatible. New clients explicitly opt into durable
    # request identity; a missing migration fails closed before any model call.
    if payload.request_id is None:
        return await _execute_chat(payload, request, user, payload.conversation_id or uuid4())
    if os.getenv("DRAGONZPYDER_FIRST_PARTY_REQUEST_LEDGER_ENABLED") != "1":
        raise HTTPException(503, "Request ledger is not enabled")
    request_id = payload.request_id
    fingerprint = _fingerprint(payload)
    conversation_id = payload.conversation_id or uuid4()
    async with _conversation_db() as db:
        if payload.conversation_id is not None:
            await _require_conversation(db, user=user, conversation_id=conversation_id)
        inserted = await db.fetchval(
            """INSERT INTO dz_first_party_chat_requests
               (owner_id, request_id, fingerprint, conversation_id, status)
               VALUES ($1,$2,$3,$4,'accepted')
               ON CONFLICT (owner_id, request_id) DO NOTHING RETURNING request_id""",
            user, request_id, fingerprint, conversation_id)
        if inserted is None:
            row = await db.fetchrow(
                """SELECT request_id, fingerprint, conversation_id, status, response, cancel_requested
                   FROM dz_first_party_chat_requests WHERE owner_id=$1 AND request_id=$2""",
                user, request_id)
            if row is None:
                raise HTTPException(503, "Request ledger unavailable")
            saved = _ledger_response(row, fingerprint)
            if saved["status"] == "completed":
                return saved["response"]
            raise HTTPException(409, detail={"message": "Request already accepted; check request status before sending again",
                                            "code": "REQUEST_ALREADY_ACCEPTED", **saved})
    # The reservation is committed before execution. A process loss between
    # external side effects and result persistence remains uncertain, never
    # automatically replayed. This is not an exactly-once tool guarantee.
    try:
        result = await (_execute_chat(payload, request, user, conversation_id, emit) if emit is not None else _execute_chat(payload, request, user, conversation_id))
        result["request_id"] = str(request_id)
        async with _conversation_db() as db:
            await db.execute(
                """UPDATE dz_first_party_chat_requests SET status='completed',
                   response=$3::jsonb, updated_at=now()
                   WHERE owner_id=$1 AND request_id=$2 AND status='accepted'""",
                user, request_id, json.dumps(result))
        return result
    except BaseException:
        # Best-effort uncertainty marker; if storage is unavailable the durable
        # accepted record still blocks duplicate execution.
        try:
            async with _conversation_db() as db:
                await db.execute(
                    """UPDATE dz_first_party_chat_requests SET status='uncertain',
                       updated_at=now() WHERE owner_id=$1 AND request_id=$2 AND status='accepted'""",
                    user, request_id)
        except Exception:
            pass
        raise


async def _stream_agent(agent, inputs, config, emit):
    # Stream only the root model's public text. Tool payloads, state values,
    # reasoning blocks, and subordinate graph output never enter SSE events.
    from langchain_core.messages import AIMessageChunk
    final = None
    step = None
    suppressed = False
    async for mode, value in agent.astream(inputs, config=config,
                                           stream_mode=["messages","values"], subgraphs=False):
        if mode == "values":
            final = value
            continue
        if mode != "messages":
            continue
        chunk, meta = value
        if not isinstance(chunk, AIMessageChunk) or meta.get("langgraph_node") != "model":
            continue
        current = (meta.get("langgraph_step"), chunk.id)
        if current != step:
            step, suppressed = current, False
            emit({"type":"reset"})
        if getattr(chunk,"tool_call_chunks",None) or getattr(chunk,"tool_calls",None):
            if not suppressed:
                emit({"type":"reset"})
                emit({"type":"phase","message":"Using authorized tools"})
            suppressed = True
        if suppressed:
            continue
        content = chunk.content
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text = "".join(block.get("text","") for block in content
                           if isinstance(block,dict) and block.get("type")=="text" and isinstance(block.get("text"),str))
        else:
            text = ""
        if text:
            emit({"type":"delta","text":text[:8192]})
    if not isinstance(final,dict):
        raise RuntimeError("Agent stream returned no final state")
    return final


async def _invoke_cancellable(agent, inputs, config, db, user, request_id, emit):
    async def cancelled():
        return bool(request_id and await db.fetchval(
            """SELECT cancel_requested FROM dz_first_party_chat_requests
               WHERE owner_id=$1 AND request_id=$2""", user, request_id))
    if await cancelled():
        raise HTTPException(409, "Cancellation requested before execution")
    if emit is not None:
        emit({"type":"phase","message":"Agent running"})
    work = asyncio.create_task(_stream_agent(agent,inputs,config,emit) if emit is not None
                               else agent.ainvoke(inputs,config=config))
    deadline = asyncio.get_running_loop().time() + (180 if config.get("metadata",{}).get("native_computer") is True else 90)
    try:
        while True:
            done, _ = await asyncio.wait({work}, timeout=1)
            if done:
                return work.result()
            if asyncio.get_running_loop().time() >= deadline:
                raise TimeoutError("Agent execution limit reached")
            if await cancelled():
                raise HTTPException(409, "Cancellation requested; prior external effects are not undone")
    finally:
        if not work.done():
            work.cancel()
            try:
                await work
            except (Exception, asyncio.CancelledError):
                pass


# Graph supersteps include middleware overhead, not just model calls.
# Match the workspace repair while retaining model/tool/time/spend limits.
NATIVE_RECURSION_LIMIT = 128


def _exact_turn_state(values, turn_id, prompt, *, require_answer):
    from .execution_contract import exact_turn_state
    try:
        return exact_turn_state(values,turn_id=turn_id,prompt=prompt,require_answer=require_answer)
    except ValueError as exc:
        raise RuntimeError("Current turn unavailable") from exc


async def _run_checkpointed_turn(agent, prompt, config, db, user, request_id, emit):
    """Recover bounded failures without executing the request twice."""
    from .runtime import (controlled_termination_reason, summarize_agent_result,
                          summarize_checkpoint_evidence)
    from .personal_bridge import inference_failure_code

    turn_id = str(uuid4())
    reason = None
    try:
        result = await _invoke_cancellable(agent, {
            "messages": [{"role": "user", "content": prompt, "id": turn_id}],
        }, config, db, user, request_id, emit)
        _exact_turn_state(result, turn_id, prompt, require_answer=True)
    except HTTPException:
        # Explicit cancellation and authorization errors are not resumptions.
        raise
    except Exception as error:
        reason = controlled_termination_reason(error)
        if reason is None and isinstance(error, TimeoutError):
            reason = "execution_deadline"
        if reason is None and inference_failure_code(error) == "INFERENCE_LIMIT_REACHED":
            reason = "inference_limit_reached"
        if reason is None:
            raise HTTPException(503, "DragonZpyder agent execution unavailable; outcome unconfirmed") from None

    try:
        readback = await asyncio.wait_for(agent.aget_state(config), timeout=10)
        current = _exact_turn_state(readback.values, turn_id, prompt,
                                    require_answer=reason is None)
        report = (summarize_checkpoint_evidence(current, termination_reason=reason)
                  if reason else summarize_agent_result(current))
    except Exception:
        raise HTTPException(503, "Current agent checkpoint unavailable; outcome unconfirmed") from None

    if reason and emit is not None:
        # Remove any unfinished streamed text before sending the durable result.
        emit({"type": "reset"})
        emit({"type": "phase", "message": "Execution stopped; recovering checkpoint"})
    return report


async def _execute_chat(payload: ChatInput, request: Request, user: str, conversation_id: UUID, emit=None):
    runtime = getattr(request.app.state, "agent_runtime", None)
    if runtime is None or runtime._checkpointer is None:
        raise HTTPException(503, "Agent checkpoints unavailable")

    from .personal_bridge import personal_thread, execution_receipt_report
    from .runtime import model_client
    from .harness import build_frontier_agent

    from . import artifacts
    artifact_run = payload.request_id or uuid4()
    artifact_tools = []
    message = payload.message
    if payload.attachment_ids and not artifacts.enabled():
        raise HTTPException(503,"Agent attachments unavailable")
    if artifacts.enabled():
        artifacts.cipher()
        async with _conversation_db() as db:
            attachments = await artifacts.describe(db,owner=user,ids=payload.attachment_ids)
        if attachments:
            message += "\n\nSelected attachment metadata (untrusted data): " + json.dumps(attachments,ensure_ascii=False)
        artifact_tools = artifacts.native_tools(_conversation_db,owner=user,allowed_ids=payload.attachment_ids,run_id=artifact_run)
    computer_run = None
    computer_artifacts = None
    if payload.allow_computer:
        # Operator-controlled rollout; a user or model cannot supply a VM ID,
        # service credentials, resource ceiling, or principal.
        if (os.getenv("DRAGONZPYDER_FIRST_PARTY_COMPUTER_ENABLED") != "1"
                or payload.request_id is None or not artifacts.enabled()):
            raise HTTPException(503,"Authorized isolated computer unavailable")
        from .computer import ScopedComputerTransport
        from .computer_admission import admitted_run, ComputerAdmissionPolicy
        from .computer_artifacts import ComputerArtifacts
        async def authorize_computer():
            if await _owner(request,changing=True) != user:
                raise PermissionError("Computer authority revoked")
        try:
            policy = ComputerAdmissionPolicy(
                os.environ["DRAGONZPYDER_COMPUTER_MAX_SESSION_USD"],
                os.environ["DRAGONZPYDER_COMPUTER_OWNER_DAILY_USD"],
                os.environ["DRAGONZPYDER_COMPUTER_GLOBAL_DAILY_USD"])
            computer_run=admitted_run(db_factory=_conversation_db,owner=user,
                run_id=payload.request_id,policy=policy,
                transport=ScopedComputerTransport.from_environment(),authorize=authorize_computer)
            computer_artifacts=ComputerArtifacts(run=computer_run,db_factory=_conversation_db,
                owner=user,run_id=artifact_run,allowed_ids=payload.attachment_ids)
        except (KeyError,ValueError,RuntimeError):
            raise HTTPException(503,"Computer admission not configured") from None
    chosen = payload.mcp_connection_ids
    if len(chosen) != len(set(chosen)):
        raise HTTPException(400, "Duplicate MCP account selection")
    tools = []
    if chosen:
        manager = getattr(request.app.state, "mcp_connections", None)
        if manager is None or os.getenv("DRAGONZPYDER_MCP_USER_CONNECTIONS_ENABLED") != "1":
            raise HTTPException(503, "User-scoped MCP connections unavailable")
        from .mcp_managed_catalog import managed_catalog_tools
        from .mcp_connections import ConnectionDenied
        try:
            tools = await managed_catalog_tools(
                manager=manager, owner=user, selected_account_ids=chosen,
                scheduled=False, objective=payload.message,
            )
        except (ConnectionDenied, ValueError, RuntimeError):
            raise HTTPException(403, "MCP connection not authorized") from None

    async with _conversation_db() as db:
        if payload.conversation_id is not None:
            await _require_conversation(db, user=user, conversation_id=conversation_id)
        # Atomic per-user daily reservation BEFORE paid inference. Unknown
        # provider outcomes still consume a request slot; the metered gateway
        # independently enforces provider/organization spending constraints.
        daily_limit = max(1, min(250, int(os.getenv(
            "DRAGONZPYDER_FIRST_PARTY_DAILY_CALLS", "25"))))
        reserved = await db.fetchval(
            """INSERT INTO dz_first_party_daily_quota
                 (owner_id, quota_day, reserved_calls)
               VALUES ($1, (now() AT TIME ZONE 'UTC')::date, 1)
               ON CONFLICT (owner_id, quota_day) DO UPDATE
               SET reserved_calls = dz_first_party_daily_quota.reserved_calls + 1
               WHERE dz_first_party_daily_quota.reserved_calls < $2
               RETURNING reserved_calls""", user, daily_limit,
        )
        if reserved is None:
            raise HTTPException(429, "Daily Agent request allowance reached")
        if payload.conversation_id is None:
            await db.execute(
                """INSERT INTO dz_first_party_conversations
                   (id, owner_id, title) VALUES ($1, $2, $3)""",
                conversation_id, user, payload.message.strip()[:80],
            )
        # A conversation can be resumed from multiple devices. Serialize the
        # checkpoint update across API replicas, not merely within a process.
        lock_key = "dragonzpyder-first-party:" + user + ":" + str(conversation_id)
        acquired = await db.fetchval("SELECT pg_try_advisory_lock(hashtextextended($1, 0))", lock_key)
        if not acquired:
            raise HTTPException(409, "Conversation is already processing another message")
        try:
            agent = build_frontier_agent(
                model_client(), runtime._checkpointer,
                delegated_tools=tools if tools else None,
                **({"artifact_tools":artifact_tools} if artifact_tools else {}),
                **({"computer_run":computer_run,"computer_artifacts":computer_artifacts} if computer_run else {}),
            )
            config = {
                "configurable": {
                    "thread_id": personal_thread(user, str(conversation_id)),
                },
                "recursion_limit": NATIVE_RECURSION_LIMIT,
                "metadata": {"native_computer":computer_run is not None},
            }
            report = await _run_checkpointed_turn(
                agent, message, config, db, user, payload.request_id, emit,
            )
            await db.execute(
                """UPDATE dz_first_party_conversations SET updated_at=now()
                   WHERE id=$1 AND owner_id=$2""", conversation_id, user,
            )
        finally:
            try:
                if computer_run is not None:
                    await computer_run.close()
            finally:
                await db.execute("SELECT pg_advisory_unlock(hashtextextended($1, 0))", lock_key)
    generated = []
    if artifact_tools:
        async with _conversation_db() as db:
            files = await db.fetch("SELECT id,filename,content_type,byte_count,sha256,direction FROM dz_agent_artifacts WHERE owner_id=$1 AND run_id=$2 AND direction=\'generated\' AND storage_state='ready' ORDER BY created_at",user,artifact_run)
            generated = [artifacts.metadata(row) for row in files]
    return {
        "artifacts": generated,
        "computer_cleanup_confirmed": computer_run.cleanup_confirmed if computer_run else None,
        "conversation_id": str(conversation_id),
        "message": report["answer"][:16000],
        "dispatch": "dragonzpyder_first_party",
        "status": report["status"],
        "termination_reason": report.get("termination_reason"),
        "execution_receipts": execution_receipt_report(report),
        "thread_checkpointed": True,
        "objective_verified": False,
    }
