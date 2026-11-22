"""First-party Personal Agent HTTP surface.

Web, Android (via Web), and future native clients enter DragonZpyder before
any optional MCP integration. No Operly session, service proof, or user-chosen
principal is accepted. This migration surface is OFF until first-party
identity, checkpoint storage, and conversation schema are deployed.
"""
from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

import asyncpg
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from identity.http_bridge import _identity_db, _issuer
from identity.sessions import SessionDenied, resolve_browser_session

router = APIRouter(prefix="/v2/personal", tags=["first-party-personal"])


class ChatInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=12000)
    conversation_id: UUID | None = None
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
            "web_cutover_enabled": (enabled and
                os.getenv("DRAGONZPYDER_FIRST_PARTY_WEB_CUTOVER_ENABLED") == "1")}


@router.get("/session")
async def session(request: Request):
    await _owner(request, changing=False)
    return {"authenticated": True, "runtime": "dragonzpyder"}


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


@router.post("/chat")
async def chat(payload: ChatInput, request: Request):
    user = await _owner(request, changing=True)
    if not payload.message.strip():
        raise HTTPException(422, "Message cannot be blank")
    runtime = getattr(request.app.state, "agent_runtime", None)
    if runtime is None or runtime._checkpointer is None:
        raise HTTPException(503, "Agent checkpoints unavailable")

    from .personal_bridge import personal_thread, execution_receipt_report
    from .runtime import model_client, summarize_agent_result
    from .harness import build_frontier_agent

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
                scheduled=False,
            )
        except (ConnectionDenied, ValueError, RuntimeError):
            raise HTTPException(403, "MCP connection not authorized") from None

    conversation_id = payload.conversation_id or uuid4()
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
            )
            config = {
                "configurable": {
                    "thread_id": personal_thread(user, str(conversation_id)),
                },
                "recursion_limit": 48,
            }
            try:
                result = await asyncio.wait_for(agent.ainvoke({
                    "messages": [{"role": "user", "content": payload.message}],
                }, config=config), timeout=90)
                report = summarize_agent_result(result)
                readback = await agent.aget_state(config)
                if not (readback.values or {}).get("messages"):
                    raise RuntimeError("Missing durable checkpoint")
            except Exception:
                raise HTTPException(503, "DragonZpyder agent execution unavailable") from None
            await db.execute(
                """UPDATE dz_first_party_conversations SET updated_at=now()
                   WHERE id=$1 AND owner_id=$2""", conversation_id, user,
            )
        finally:
            await db.execute("SELECT pg_advisory_unlock(hashtextextended($1, 0))", lock_key)
    return {
        "conversation_id": str(conversation_id),
        "message": report["answer"][:16000],
        "dispatch": "dragonzpyder_first_party",
        "execution_receipts": execution_receipt_report(report),
        "thread_checkpointed": True,
        "objective_verified": False,
    }
