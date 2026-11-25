"""Operator-only personal transcript migration; never replay messages into a graph.

Source is a scoped read-only export. Archive is display-only, not a checkpoint,
tool grant, session, approval or source of instructions. No raw rows in logs.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from uuid import UUID

from cryptography.fernet import Fernet

FORMAT = "dz-operly-personal-history-v1"
MAX_BYTES = 16 * 1024 * 1024
TTL = 24 * 60 * 60


class HistoryConflict(ValueError):
    pass


def _uuid(value):
    if not isinstance(value, str) or str(UUID(value)) != value:
        raise HistoryConflict("Noncanonical identifier")
    return value


def _utc(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
        if value.tzinfo is None:
            raise HistoryConflict("Missing timestamp timezone")
    if not isinstance(value, datetime):
        raise HistoryConflict("Invalid timestamp")
    return value.replace(tzinfo=timezone.utc).astimezone(timezone.utc).isoformat()


def _text(value, limit, *, empty=False):
    if (not isinstance(value, str) or len(value.encode("utf-8")) > limit
            or (not empty and not value.strip()) or "\x00" in value):
        raise HistoryConflict("Invalid transcript field")
    return value


def prepare_history(conversations, messages, *, expected_conversations, expected_messages):
    if (type(expected_conversations) is not int or type(expected_messages) is not int
            or not 1 <= expected_conversations <= 10000 or not 0 <= expected_messages <= 100000
            or len(conversations) != expected_conversations or len(messages) != expected_messages):
        raise HistoryConflict("Unapproved history inventory")
    owners = {}
    convs = []
    for row in conversations:
        if set(row) != {"id","owner_id","title","created_at","updated_at","channel","surface"}:
            raise HistoryConflict("Invalid conversation shape")
        cid, owner = _uuid(row["id"]), _uuid(row["owner_id"])
        if cid in owners:
            raise HistoryConflict("Duplicate conversation")
        owners[cid] = owner
        convs.append({"id":cid,"owner_id":owner,"title":_text(row["title"],1000),
            "created_at":_utc(row["created_at"]),"updated_at":_utc(row["updated_at"]),
            "channel":_text(row["channel"],160),"surface":_text(row["surface"],160)})
    seen = set()
    msgs = []
    for row in messages:
        if set(row) != {"id","conversation_id","owner_id","role","content","created_at"}:
            raise HistoryConflict("Invalid message shape")
        mid, cid, owner = _uuid(row["id"]), _uuid(row["conversation_id"]), _uuid(row["owner_id"])
        if mid in seen or owners.get(cid) != owner or row["role"] not in ("user","assistant"):
            raise HistoryConflict("Duplicate, orphaned, non-display or cross-owner message")
        seen.add(mid)
        msgs.append({"id":mid,"conversation_id":cid,"owner_id":owner,"role":row["role"],
                     "content":_text(row["content"],1024*1024,empty=True),
                     "created_at":_utc(row["created_at"])})
    return {"format":FORMAT,"conversations":sorted(convs,key=lambda r:r["id"]),
            "messages":sorted(msgs,key=lambda r:(r["conversation_id"],r["created_at"],r["id"]))}


def seal_history(bundle, key):
    raw=json.dumps(bundle,ensure_ascii=False,separators=(",",":")).encode("utf-8")
    if len(raw)>MAX_BYTES//2:
        raise HistoryConflict("Transcript archive too large for reviewed transfer")
    token=Fernet(key).encrypt(raw)
    if len(token)>MAX_BYTES:
        raise HistoryConflict("Encrypted archive too large")
    return token


def open_history(token, key, checksum, *, expected_conversations, expected_messages):
    if not 0<len(token)<=MAX_BYTES or not hmac.compare_digest(hashlib.sha256(token).hexdigest(),checksum):
        raise HistoryConflict("Archive integrity mismatch")
    data=json.loads(Fernet(key).decrypt(token,ttl=TTL))
    if not isinstance(data,dict) or set(data)!={"format","conversations","messages"} or data["format"]!=FORMAT:
        raise HistoryConflict("Unexpected archive format")
    return prepare_history(data["conversations"],data["messages"],
        expected_conversations=expected_conversations,expected_messages=expected_messages)


async def read_history_source(conn, *, expected_conversations, expected_messages):
    async with conn.transaction(isolation="repeatable_read",readonly=True):
        if await conn.fetchval("""
            SELECT current_user='dz_personal_history_export' AND session_user=current_user
              AND current_setting('transaction_read_only')='on'
              AND to_regclass('public.agent_chat_conversations') IS NOT NULL
              AND to_regclass('public.identity_accounts') IS NULL
              AND NOT (r.rolsuper OR r.rolcreatedb OR r.rolcreaterole OR r.rolbypassrls OR r.rolreplication OR r.rolinherit)
              AND NOT EXISTS (SELECT 1 FROM pg_auth_members m WHERE m.member=r.oid)
              AND NOT has_database_privilege(current_user,current_database(),'CREATE')
              AND NOT has_schema_privilege(current_user,'public','CREATE')
              AND NOT EXISTS (
                SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','f')
                AND (c.relowner=r.oid OR has_any_column_privilege(current_user,c.oid,'INSERT,UPDATE,REFERENCES')
                 OR has_table_privilege(current_user,c.oid,'DELETE,TRUNCATE,TRIGGER')
                 OR (c.relname NOT IN ('dz_personal_history_export_conversations','dz_personal_history_export_messages')
                     AND has_any_column_privilege(current_user,c.oid,'SELECT'))))
              FROM pg_roles r WHERE r.rolname=current_user
        """) is not True:
            raise HistoryConflict("Unexpected source export authority")
        convs=await conn.fetch("SELECT * FROM public.dz_personal_history_export_conversations ORDER BY id")
        msgs=await conn.fetch("SELECT * FROM public.dz_personal_history_export_messages ORDER BY conversation_id,created_at,id")
        return prepare_history([dict(r) for r in convs],[dict(r) for r in msgs],
            expected_conversations=expected_conversations,expected_messages=expected_messages)


async def import_history(conn, bundle, *, approved_owners, operator_approved=False):
    """Approved owners come from an independently verified identity snapshot.

    Never trust owner IDs merely because an encrypted file claims them. Archive
    import is insert-only and leaves first-party conversation/checkpoint tables
    untouched. Runtime read access is separately gated and reviewed.
    """
    if not operator_approved:
        raise PermissionError("Explicit archive import approval required")
    if not approved_owners or any(r["owner_id"] not in approved_owners for r in bundle["conversations"]):
        raise HistoryConflict("Unknown imported owner")
    bundle=prepare_history(bundle["conversations"],bundle["messages"],
        expected_conversations=len(bundle["conversations"]),expected_messages=len(bundle["messages"]))
    async with conn.transaction(isolation="serializable"):
        await conn.execute("SELECT pg_advisory_xact_lock(739110212)")
        if await conn.fetchval("""
            SELECT current_user='dz_personal_history_import' AND session_user=current_user
              AND to_regclass('public.agent_chat_conversations') IS NULL
              AND to_regclass('public.identity_accounts') IS NULL
              AND to_regclass('public.dz_first_party_conversations') IS NOT NULL
              AND NOT (r.rolsuper OR r.rolcreatedb OR r.rolcreaterole OR r.rolbypassrls OR r.rolreplication OR r.rolinherit)
              AND NOT EXISTS (SELECT 1 FROM pg_auth_members m WHERE m.member=r.oid)
              AND NOT has_database_privilege(current_user,current_database(),'CREATE')
              AND NOT has_schema_privilege(current_user,'public','CREATE')
              AND NOT EXISTS (
                SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','f')
                  AND (c.relowner=r.oid OR has_any_column_privilege(current_user,c.oid,'UPDATE,REFERENCES')
                   OR has_table_privilege(current_user,c.oid,'DELETE,TRUNCATE,TRIGGER')
                   OR (c.relname NOT IN ('dz_imported_personal_conversations','dz_imported_personal_messages')
                       AND has_any_column_privilege(current_user,c.oid,'INSERT'))))
              FROM pg_roles r WHERE r.rolname=current_user
        """) is not True:
            raise HistoryConflict("Unexpected archive import authority")
        for table in ("dz_imported_personal_conversations","dz_imported_personal_messages"):
            if await conn.fetchval("SELECT count(*) FROM public."+table):
                raise HistoryConflict("Archive is not empty")
        for row in bundle["conversations"]:
            # An existing live row with different owner must block the import.
            owner=await conn.fetchval("SELECT owner_id FROM public.dz_first_party_conversations WHERE id=$1",UUID(row["id"]))
            if owner is not None and owner!=row["owner_id"]:
                raise HistoryConflict("Existing first-party owner conflicts")
            await conn.execute("""
                INSERT INTO public.dz_imported_personal_conversations
                 (id,owner_id,title,created_at,updated_at,channel,surface)
                VALUES($1,$2,$3,$4,$5,$6,$7)
            """,UUID(row["id"]),row["owner_id"],row["title"],datetime.fromisoformat(row["created_at"]),
                  datetime.fromisoformat(row["updated_at"]),row["channel"],row["surface"])
        for row in bundle["messages"]:
            await conn.execute("""
                INSERT INTO public.dz_imported_personal_messages(id,conversation_id,owner_id,role,content,created_at)
                VALUES($1,$2,$3,$4,$5,$6)
            """,UUID(row["id"]),UUID(row["conversation_id"]),row["owner_id"],row["role"],row["content"],datetime.fromisoformat(row["created_at"]))
        # Full-field readback in the same transaction, not count-only success.
        c=await conn.fetch("SELECT id::text,owner_id,title,created_at,updated_at,channel,surface FROM public.dz_imported_personal_conversations")
        m=await conn.fetch("SELECT id::text,conversation_id::text,owner_id,role,content,created_at FROM public.dz_imported_personal_messages")
        check=prepare_history([dict(r) for r in c],[dict(r) for r in m],
            expected_conversations=len(bundle["conversations"]),expected_messages=len(bundle["messages"]))
        if check!=bundle:
            raise HistoryConflict("Archive readback mismatch")
    return {"conversations":len(bundle["conversations"]),"messages":len(bundle["messages"])}


async def read_approved_owners(conn, *, expected_accounts):
    from identity.http_bridge import _restricted_identity_role
    await _restricted_identity_role(conn)
    async with conn.transaction(isolation="repeatable_read",readonly=True):
        if await conn.fetchval("""
            SELECT to_regclass('public.app_users') IS NULL
              AND EXISTS (SELECT 1 FROM pg_constraint
                WHERE conrelid=to_regclass('public.identity_accounts')
                AND conname='identity_import_not_automatically_active' AND convalidated)
              AND NOT EXISTS (SELECT 1 FROM public.identity_accounts
                WHERE identity_origin<>'operly_import' OR source_operly_user_id IS DISTINCT FROM subject OR status<>'pending')
              AND NOT EXISTS(SELECT 1 FROM public.identity_oauth_clients WHERE enabled)
        """) is not True:
            raise HistoryConflict("Identity owner inventory is not fenced")
        rows=await conn.fetch("SELECT subject FROM public.identity_accounts")
        owners={_uuid(row["subject"]) for row in rows}
        if len(owners)!=expected_accounts or len(rows)!=expected_accounts:
            raise HistoryConflict("Identity owner count mismatch")
        return owners


async def run(args,key):
    import os
    import asyncpg
    from identity.offline_transfer import _read_private, _write_private
    if args.mode=="export":
        conn=await asyncpg.connect(os.environ["OPERLY_PERSONAL_HISTORY_EXPORT_DSN"],timeout=10,command_timeout=30)
        try:
            bundle=await read_history_source(conn,expected_conversations=args.expected_conversations,
                                              expected_messages=args.expected_messages)
        finally:
            await conn.close()
        token=seal_history(bundle,key)
        _write_private(args.package,token)
        return {"conversations":len(bundle["conversations"]),"messages":len(bundle["messages"]),
                "package_sha256":hashlib.sha256(token).hexdigest()}
    bundle=open_history(_read_private(args.package),key,args.expected_sha256,
        expected_conversations=args.expected_conversations,expected_messages=args.expected_messages)
    identity=await asyncpg.connect(os.environ["DRAGONZPYDER_IDENTITY_DATABASE_URL"],timeout=10,command_timeout=30)
    try:
        owners=await read_approved_owners(identity,expected_accounts=args.expected_accounts)
    finally:
        await identity.close()
    conn=await asyncpg.connect(os.environ["DRAGONZPYDER_HISTORY_IMPORT_DSN"],timeout=10,command_timeout=60)
    try:
        return await import_history(conn,bundle,approved_owners=owners,operator_approved=True)
    finally:
        await conn.close()


def main():
    import argparse
    import asyncio
    from identity.offline_transfer import _key
    parser=argparse.ArgumentParser(description="Isolated personal transcript archive transfer")
    sub=parser.add_subparsers(dest="mode",required=True)
    for mode in ("export","import"):
        p=sub.add_parser(mode)
        p.add_argument("--package",required=True)
        p.add_argument("--expected-conversations",type=int,required=True)
        p.add_argument("--expected-messages",type=int,required=True)
        p.add_argument("--approve-history-transfer",action="store_true",required=True)
        if mode=="import":
            p.add_argument("--expected-accounts",type=int,required=True)
            p.add_argument("--expected-sha256",required=True)
    args=parser.parse_args()
    try:
        result=asyncio.run(run(args,_key()))
    except Exception:
        print("PERSONAL_HISTORY_TRANSFER_FAILED")
        raise SystemExit(1) from None
    print(json.dumps(result,sort_keys=True))
    print("PERSONAL_HISTORY_TRANSFER_COMPLETE")


if __name__=="__main__":
    main()
