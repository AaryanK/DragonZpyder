"""Read-only personal history archive. Never replay archived content into agents."""
from __future__ import annotations

import os
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response

from identity.http_bridge import _enabled as _identity_enabled
from .first_party_chat import _conversation_db, _owner

router = APIRouter(prefix="/v2/personal/archive", tags=["personal-history"])


def _archive_enabled():
    if os.getenv("DRAGONZPYDER_PERSONAL_HISTORY_ARCHIVE_ENABLED") != "1":
        raise HTTPException(404, "Not found")
    _identity_enabled()


@router.get("/conversations")
async def archive_conversations(request: Request, response: Response, offset: int = 0):
    _archive_enabled()
    response.headers["Cache-Control"] = "no-store"
    owner = await _owner(request, changing=False)
    if not 0 <= offset <= 10000:
        raise HTTPException(400, "Invalid page")
    async with _conversation_db() as db:
        rows = await db.fetch("""
            SELECT id,title,created_at,updated_at,channel,surface
            FROM public.dz_imported_personal_conversations
            WHERE owner_id=$1 ORDER BY updated_at DESC,id LIMIT 101 OFFSET $2
        """, owner, offset)
    return {"conversations":[{"id":str(r["id"]),"title":r["title"],
        "created_at":r["created_at"].isoformat(),"updated_at":r["updated_at"].isoformat(),
        "channel":r["channel"],"surface":r["surface"],"archived":True}
        for r in rows[:100]],"next_offset":offset+100 if len(rows)>100 else None}


@router.get("/conversations/{conversation_id}/messages")
async def archive_messages(conversation_id: UUID, request: Request, offset: int = 0):
    _archive_enabled()
    owner = await _owner(request, changing=False)
    if not 0 <= offset <= 100000:
        raise HTTPException(400, "Invalid page")
    async with _conversation_db() as db:
        exists = await db.fetchval("""
            SELECT EXISTS(SELECT 1 FROM public.dz_imported_personal_conversations
                          WHERE id=$1 AND owner_id=$2)
        """, conversation_id, owner)
        if not exists:
            raise HTTPException(404, "Conversation not found")
        rows = await db.fetch("""
            SELECT id,role,content,created_at FROM public.dz_imported_personal_messages
            WHERE conversation_id=$1 AND owner_id=$2
            ORDER BY created_at,id LIMIT 11 OFFSET $3
        """, conversation_id, owner, offset)
    return {"messages":[{"id":str(r["id"]),"role":r["role"],"content":r["content"],
             "created_at":r["created_at"].isoformat()} for r in rows[:10]],
             "archived":True,"next_offset":offset+10 if len(rows)>10 else None}
