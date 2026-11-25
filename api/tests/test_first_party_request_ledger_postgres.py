"""Real database concurrency/replay check; no inference or external tool calls."""
import asyncio
import os
from pathlib import Path
from uuid import uuid4
import asyncpg
import pytest
from fastapi import HTTPException
from agent_platform import first_party_chat as native

DSN=os.getenv("DRAGONZPYDER_BUDGET_TEST_DSN")
pytestmark=pytest.mark.skipif(not DSN,reason="Requires disposable CI PostgreSQL")

def test_real_ledger_reservation_and_uncertain_recovery(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_AGENT_DATABASE_URL",DSN)
    monkeypatch.setenv("DRAGONZPYDER_FIRST_PARTY_REQUEST_LEDGER_ENABLED","1")
    async def scenario():
        db=await asyncpg.connect(DSN)
        migration=Path(__file__).resolve().parents[1]/"agent_platform/migrations/20261125_first_party_request_ledger.sql"
        owner="ci-"+str(uuid4())
        rid=uuid4()
        try:
            await db.execute(migration.read_text())
            entered=asyncio.Event()
            release=asyncio.Event()
            executions=[]
            async def fake(payload,request,user,conversation):
                executions.append(user)
                entered.set()
                await release.wait()
                return {"conversation_id":str(conversation),"message":"done"}
            monkeypatch.setattr(native,"_execute_chat",fake)
            payload=native.ChatInput(message="test",request_id=rid)
            first=asyncio.create_task(native._chat_owned(payload,object(),owner))
            await asyncio.wait_for(entered.wait(),5)
            try:
                with pytest.raises(HTTPException) as concurrent:
                    await native._chat_owned(payload,object(),owner)
                assert concurrent.value.status_code==409
            finally:
                release.set()
            result=await first
            assert await native._chat_owned(payload,object(),owner)==result
            assert executions==[owner]
            with pytest.raises(HTTPException) as conflict:
                await native._chat_owned(native.ChatInput(message="changed",request_id=rid),object(),owner)
            assert conflict.value.status_code==409
            assert not await db.fetchval("SELECT EXISTS(SELECT 1 FROM dz_first_party_chat_requests WHERE owner_id=$1 AND request_id=$2)",owner+"-other",rid)
            unknown=native.ChatInput(message="unknown",request_id=uuid4())
            async def fail(*args):raise RuntimeError("simulated outcome loss")
            monkeypatch.setattr(native,"_execute_chat",fail)
            with pytest.raises(RuntimeError):await native._chat_owned(unknown,object(),owner)
            assert await db.fetchval("SELECT status FROM dz_first_party_chat_requests WHERE owner_id=$1 AND request_id=$2",owner,unknown.request_id)=="uncertain"
            with pytest.raises(HTTPException) as replay:await native._chat_owned(unknown,object(),owner)
            assert replay.value.status_code==409
        finally:
            await db.execute("DELETE FROM dz_first_party_chat_requests WHERE owner_id=$1",owner)
            await db.close()
    asyncio.run(scenario())
