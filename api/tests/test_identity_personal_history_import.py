"""Synthetic encrypted personal history and real PostgreSQL archive contracts."""
import hashlib
import os
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4, UUID
from urllib.parse import urlsplit

import pytest
from cryptography.fernet import Fernet, InvalidToken

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agent_platform.personal_history_import import (
    HistoryConflict, prepare_history, seal_history, open_history,
    read_history_source, import_history,
)

MIGRATIONS=Path(__file__).resolve().parents[1]/"agent_platform"/"migrations"


def sample():
    owner,cid,mid=[str(uuid4()) for _ in range(3)]
    now=datetime.now(timezone.utc)
    return prepare_history(
        [{"id":cid,"owner_id":owner,"title":"Synthetic title","created_at":now,
          "updated_at":now,"channel":"web","surface":"personal"}],
        [{"id":mid,"conversation_id":cid,"owner_id":owner,"role":"user","content":"Synthetic message",
          "created_at":now}],expected_conversations=1,expected_messages=1)


def test_encrypted_roundtrip():
    bundle=sample()
    key=Fernet.generate_key()
    token=seal_history(bundle,key)
    digest=hashlib.sha256(token).hexdigest()
    assert b"Synthetic message" not in token
    assert open_history(token,key,digest,expected_conversations=1,expected_messages=1)==bundle
    with pytest.raises(HistoryConflict):
        open_history(token,key,"0"*64,expected_conversations=1,expected_messages=1)
    with pytest.raises(InvalidToken):
        open_history(token,Fernet.generate_key(),digest,expected_conversations=1,expected_messages=1)
    with pytest.raises(HistoryConflict):
        open_history(token,key,digest,expected_conversations=1,expected_messages=2)


@pytest.mark.parametrize("field,value",[
    ("owner_id",str(uuid4())),("conversation_id",str(uuid4())),("role","tool"),("role","system")])
def test_bad_message_refused(field,value):
    bundle=sample()
    bundle["messages"][0][field]=value
    with pytest.raises(HistoryConflict):
        prepare_history(bundle["conversations"],bundle["messages"],expected_conversations=1,expected_messages=1)


@pytest.mark.asyncio
async def test_scoped_history_transfer_disposable_postgres():
    import asyncpg
    dsn=os.getenv("DRAGONZPYDER_IDENTITY_TEST_DSN","")
    if not dsn:
        pytest.skip("No disposable PostgreSQL")
    if urlsplit(dsn).path!="/identity_test":
        raise RuntimeError("Never run against production")
    conn=await asyncpg.connect(dsn)
    b=sample()
    c,m=b["conversations"][0],b["messages"][0]
    other,workspace,workspace_msg=[str(uuid4()) for _ in range(3)]
    try:
        assert await conn.fetchval("SELECT to_regclass('public.app_users') IS NULL AND to_regclass('public.dz_first_party_conversations') IS NULL")
        await conn.execute("""
            CREATE TABLE public.app_users(id text PRIMARY KEY);
            CREATE TABLE public.agent_chat_conversations(
              id text PRIMARY KEY,owner_user_id text,workspace_id text,authority_user_id text,
              scope_kind text,title text,created_at timestamptz,updated_at timestamptz,channel text,surface text);
            CREATE TABLE public.agent_chat_messages(
              id text PRIMARY KEY,conversation_id text,role text,content text,created_at timestamptz);
        """)
        await conn.execute("INSERT INTO public.app_users VALUES($1),($2)",c["owner_id"],other)
        await conn.execute("""
            INSERT INTO public.agent_chat_conversations VALUES
            ($1,$2,NULL,$2,'personal',$3,$4,$5,$6,$7),
            ($8,NULL,$9,$2,'workspace','Private workspace',$4,$5,$6,$7)
        """,c["id"],c["owner_id"],c["title"],datetime.fromisoformat(c["created_at"]),
             datetime.fromisoformat(c["updated_at"]),c["channel"],c["surface"],workspace,other)
        await conn.execute("INSERT INTO public.agent_chat_messages VALUES($1,$2,$3,$4,$5),($6,$7,'user','Business secret',$5)",
            m["id"],c["id"],m["role"],m["content"],datetime.fromisoformat(m["created_at"]),workspace_msg,workspace)
        await conn.execute((MIGRATIONS/"operly_personal_history_export_role_manual.sql").read_text())
        await conn.execute("SET SESSION AUTHORIZATION dz_personal_history_export")
        try:
            exported=await read_history_source(conn,expected_conversations=1,expected_messages=1)
            assert exported==b
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await conn.fetch("SELECT * FROM public.agent_chat_messages")
        finally:
            await conn.execute("RESET SESSION AUTHORIZATION")
        await conn.execute("""
            DROP VIEW public.dz_personal_history_export_messages,public.dz_personal_history_export_conversations;
            DROP TABLE public.agent_chat_messages,public.agent_chat_conversations,public.app_users;
            DROP OWNED BY dz_personal_history_export;
            DROP ROLE dz_personal_history_export;
        """)
        await conn.execute((MIGRATIONS/"20261122_first_party_chat.sql").read_text())
        await conn.execute((MIGRATIONS/"20261125_personal_history_archive_manual.sql").read_text())
        await conn.execute("INSERT INTO public.dz_first_party_conversations(id,owner_id,title) VALUES($1,$2,'Existing')",UUID(c["id"]),other)
        await conn.execute("SET SESSION AUTHORIZATION dz_personal_history_import")
        try:
            with pytest.raises(HistoryConflict):
                await import_history(conn,b,approved_owners={other},operator_approved=True)
            with pytest.raises(HistoryConflict):
                await import_history(conn,b,approved_owners={c["owner_id"]},operator_approved=True)
            assert await conn.fetchval("SELECT count(*) FROM public.dz_imported_personal_conversations")==0
        finally:
            await conn.execute("RESET SESSION AUTHORIZATION")
        await conn.execute("UPDATE public.dz_first_party_conversations SET owner_id=$1",c["owner_id"])
        await conn.execute("SET SESSION AUTHORIZATION dz_personal_history_import")
        try:
            assert await import_history(conn,b,approved_owners={c["owner_id"]},operator_approved=True)=={"conversations":1,"messages":1}
            with pytest.raises(HistoryConflict):
                await import_history(conn,b,approved_owners={c["owner_id"]},operator_approved=True)
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await conn.execute("DELETE FROM public.dz_imported_personal_messages")
            with pytest.raises(asyncpg.ForeignKeyViolationError):
                await conn.execute("INSERT INTO public.dz_imported_personal_messages VALUES($1,$2,$3,'user','bad',now())",uuid4(),UUID(c["id"]),other)
        finally:
            await conn.execute("RESET SESSION AUTHORIZATION")
        assert await conn.fetchval("SELECT content FROM public.dz_imported_personal_messages")==m["content"]
        assert await conn.fetchval("SELECT title FROM public.dz_first_party_conversations")=="Existing"
    finally:
        await conn.execute("""
          DROP VIEW IF EXISTS public.dz_personal_history_export_messages,public.dz_personal_history_export_conversations;
          DROP TABLE IF EXISTS public.agent_chat_messages,public.agent_chat_conversations,public.app_users,
            public.dz_imported_personal_messages,public.dz_imported_personal_conversations,
            public.dz_first_party_conversations,public.dz_first_party_daily_quota;
          DO $$ BEGIN
           IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='dz_personal_history_export') THEN
             DROP OWNED BY dz_personal_history_export; DROP ROLE dz_personal_history_export;
           END IF;
           IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='dz_personal_history_import') THEN
             DROP OWNED BY dz_personal_history_import; DROP ROLE dz_personal_history_import;
           END IF;
          END $$;
        """)
        await conn.close()
