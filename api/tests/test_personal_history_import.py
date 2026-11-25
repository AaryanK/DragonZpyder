"""Offline archive ownership and import scope tests."""
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
from fastapi import HTTPException
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agent_platform import first_party_chat as chat
from agent_platform.personal_history_import import prepare, import_history, HistoryConflict

def source():
    now=datetime.now(timezone.utc)
    conversation={"id":str(uuid4()),"owner_user_id":str(uuid4()),"scope_kind":"personal","workspace_id":None,
                  "title":"Legacy","created_at":now,"updated_at":now}
    message={"id":str(uuid4()),"conversation_id":conversation["id"],"role":"user","content":"Private test","created_at":now}
    return conversation,message

def test_scope_role_and_count_checks():
    c,m=source()
    rows,messages=prepare([c],[m],1,1)
    assert rows[0][1]==c["owner_user_id"] and messages[0][3]=="Private test"
    with pytest.raises(HistoryConflict): prepare([c],[m],1,2)
    with pytest.raises(HistoryConflict): prepare([{**c,"scope_kind":"workspace"}],[m],1,1)
    with pytest.raises(HistoryConflict): prepare([c],[{**m,"role":"tool"}],1,1)
    with pytest.raises(HistoryConflict): prepare([c],[{**m,"conversation_id":str(uuid4())}],1,1)

@pytest.mark.asyncio
async def test_import_needs_approval(monkeypatch):
    monkeypatch.delenv("DRAGONZPYDER_PERSONAL_HISTORY_IMPORT",raising=False)
    with pytest.raises(PermissionError): await import_history(None,None,([],[]),approved=True)

@pytest.mark.asyncio
async def test_archive_read_requires_owner_no_runtime(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_PERSONAL_HISTORY_ARCHIVE_ENABLED","1")
    ident=uuid4()
    owner=AsyncMock(return_value="owner")
    monkeypatch.setattr(chat,"_owner",owner)
    class DB:
        async def fetchrow(self,query,*args):
            assert "owner_id=$2" in query and args==(ident,"owner")
            return {"id":ident,"archived_import":True}
        async def fetch(self,query,*args):
            assert "c.owner_id=$2" in query and args==(ident,"owner")
            return [{"role":"user","content":"Private test"}]
    @asynccontextmanager
    async def db(): yield DB()
    monkeypatch.setattr(chat,"_conversation_db",db)
    assert await chat.messages(ident,SimpleNamespace())=={"messages":[{"role":"user","content":"Private test"}],"archived_import":True}
    owner.assert_awaited_once()
    class ForeignDB:
        async def fetchrow(self,query,*args): return None
    @asynccontextmanager
    async def foreign(): yield ForeignDB()
    monkeypatch.setattr(chat,"_conversation_db",foreign)
    with pytest.raises(HTTPException) as exc: await chat.messages(ident,SimpleNamespace())
    assert exc.value.status_code==404
