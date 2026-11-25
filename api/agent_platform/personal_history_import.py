"""Offline operator-only personal transcript import, not checkpoint fabrication.

Source contains only personal-scope conversations. Existing conversations
and checkpoints are never overwritten. Archived transcripts are read-only.
No raw transcript data or connection credentials are logged.
"""
from __future__ import annotations
import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
from uuid import UUID
import asyncpg

class HistoryConflict(ValueError):
    pass

def canonical(value):
    try:
        result = UUID(value)
        if str(result) != value:
            raise ValueError()
        return result
    except (ValueError, TypeError, AttributeError):
        raise HistoryConflict("Noncanonical legacy UUID requires reviewed mapping") from None

def utc(value):
    if not isinstance(value, datetime):
        raise HistoryConflict("Invalid source timestamp")
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

def prepare(conversations, messages, expected_conversations, expected_messages):
    if len(conversations) != expected_conversations or len(messages) != expected_messages:
        raise HistoryConflict("Source inventory changed")
    if expected_conversations < 1:
        raise HistoryConflict("Empty history import refused")
    owners = {}
    result = []
    for row in conversations:
        ident, owner = canonical(row["id"]), canonical(row["owner_user_id"])
        if ident in owners or row["scope_kind"] != "personal" or row["workspace_id"] is not None:
            raise HistoryConflict("Ambiguous or nonpersonal conversation")
        title = row["title"]
        if not isinstance(title, str):
            raise HistoryConflict("Invalid title")
        owners[ident] = owner
        result.append((ident, str(owner), title.strip()[:80] or "Imported conversation",
                       utc(row["created_at"]), utc(row["updated_at"])))
    transcripts = []
    seen = set()
    for row in messages:
        ident, message_id = canonical(row["conversation_id"]), canonical(row["id"])
        if ident not in owners or message_id in seen:
            raise HistoryConflict("Orphaned or duplicate message")
        if row["role"] not in ("user","assistant") or not isinstance(row["content"],str):
            raise HistoryConflict("Unsupported message role or content; do not silently discard")
        seen.add(message_id)
        transcripts.append((ident, message_id, row["role"], row["content"], utc(row["created_at"])))
    transcripts.sort(key=lambda row: (row[0], row[4], row[1]))
    return result, transcripts

async def read_source(source, expected_conversations, expected_messages):
    async with source.transaction(isolation="repeatable_read",readonly=True):
        if not await source.fetchval("""
            SELECT current_setting('transaction_read_only')='on'
              AND to_regclass('public.agent_chat_conversations') IS NOT NULL
              AND to_regclass('public.dz_first_party_conversations') IS NULL
        """):
            raise HistoryConflict("Unexpected source database")
        rows = await source.fetch("""
            SELECT c.id,c.owner_user_id,c.scope_kind,c.workspace_id,c.title,c.created_at,c.updated_at
            FROM public.agent_chat_conversations c
            WHERE c.scope_kind='personal' AND c.workspace_id IS NULL
              AND c.owner_user_id IS NOT NULL
        """)
        messages = await source.fetch("""
            SELECT m.id,m.conversation_id,m.role,m.content,m.created_at
            FROM public.agent_chat_messages m
            JOIN public.agent_chat_conversations c ON c.id=m.conversation_id
            WHERE c.scope_kind='personal' AND c.workspace_id IS NULL
              AND c.owner_user_id IS NOT NULL
        """)
        return prepare(rows,messages,expected_conversations,expected_messages)

async def import_history(target, identities, bundle, *, approved=False):
    if not approved or os.getenv("DRAGONZPYDER_PERSONAL_HISTORY_IMPORT") != "1":
        raise PermissionError("Explicit archive import approval required")
    rows, messages = bundle
    if not rows:
        raise HistoryConflict("Empty history import refused")
    # Identity records are independently imported; no auto-create or email match.
    async with identities.transaction(isolation="repeatable_read",readonly=True):
        if not await identities.fetchval("""
            SELECT current_setting('transaction_read_only')='on'
              AND to_regclass('public.identity_accounts') IS NOT NULL
        """):
            raise HistoryConflict("Unexpected identity database")
        subjects = {r["subject"] for r in await identities.fetch("""
            SELECT subject FROM public.identity_accounts
            WHERE identity_origin='operly_import' AND source_operly_user_id=subject
              AND source_active AND status IN ('pending','active')
        """)}
        if not {r[1] for r in rows}.issubset(subjects):
            raise HistoryConflict("Owner lacks reconciled imported identity")
        async with target.transaction():
            await target.execute("SELECT pg_advisory_xact_lock(739110215)")
            if not await target.fetchval("""
                SELECT to_regclass('public.dz_imported_personal_messages') IS NOT NULL
                  AND to_regclass('public.dz_first_party_conversations') IS NOT NULL
                  AND to_regclass('public.identity_accounts') IS NULL
            """):
                raise HistoryConflict("Unexpected archive destination")
            ids = [row[0] for row in rows]
            if await target.fetchval("SELECT count(*) FROM public.dz_first_party_conversations WHERE id=ANY($1::uuid[])",ids):
                raise HistoryConflict("Target conversation collision; nothing overwritten")
            await target.executemany("""
                INSERT INTO public.dz_first_party_conversations
                (id,owner_id,title,created_at,updated_at,archived_import)
                VALUES ($1,$2,$3,$4,$5,true)
            """, rows)
            ordinals = {}
            data = []
            for ident, message_id, role, content, created in messages:
                ordinal = ordinals.get(ident,0)+1
                ordinals[ident]=ordinal
                data.append((ident,message_id,ordinal,role,content,created))
            if data:
                await target.executemany("""
                    INSERT INTO public.dz_imported_personal_messages
                    (conversation_id,source_message_id,ordinal,role,content,created_at)
                    VALUES ($1,$2,$3,$4,$5,$6)
                """,data)
            actual = await target.fetchval("SELECT count(*) FROM public.dz_imported_personal_messages WHERE conversation_id=ANY($1::uuid[])",ids)
            count = await target.fetchval("SELECT count(*) FROM public.dz_first_party_conversations WHERE id=ANY($1::uuid[]) AND archived_import",ids)
            if (count,actual)!=(len(rows),len(messages)):
                raise HistoryConflict("Archive readback count mismatch")
    return {"conversations":count,"messages":actual}

async def run(args):
    if not args.approve_archive or os.getenv("DRAGONZPYDER_PERSONAL_HISTORY_IMPORT") != "1":
        raise PermissionError("Explicit archive import approval required")
    dsns=[os.environ[k] for k in ("OPERLY_HISTORY_EXPORT_DSN","DRAGONZPYDER_IDENTITY_MIGRATION_DSN","DRAGONZPYDER_HISTORY_MIGRATION_DSN")]
    if len(set(dsns))!=3 or not all(dsns):
        raise HistoryConflict("Three distinct authorized database connections required")
    source=await asyncpg.connect(dsns[0],timeout=10,command_timeout=30)
    try:
        bundle=await read_source(source,args.expected_conversations,args.expected_messages)
    finally:
        await source.close()
    identity=await asyncpg.connect(dsns[1],timeout=10,command_timeout=30)
    try:
        target=await asyncpg.connect(dsns[2],timeout=10,command_timeout=30)
        try:
            return await import_history(target,identity,bundle,approved=True)
        finally:
            await target.close()
    finally:
        await identity.close()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--expected-conversations",type=int,required=True)
    parser.add_argument("--expected-messages",type=int,required=True)
    parser.add_argument("--approve-archive",action="store_true")
    args=parser.parse_args()
    try:
        result=asyncio.run(run(args))
    except Exception:
        print("PERSONAL_HISTORY_IMPORT_FAILED")
        raise SystemExit(1) from None
    print(json.dumps(result,sort_keys=True))
    print("PERSONAL_HISTORY_IMPORT_COMPLETE")

if __name__=="__main__":
    main()
