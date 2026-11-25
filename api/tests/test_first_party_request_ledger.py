"""No paid inference: simulate concurrent retry, replay and failed execution."""
import asyncio
from contextlib import asynccontextmanager
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from agent_platform import first_party_chat as native


class LedgerDB:
    def __init__(self):
        self.rows = {}

    async def fetchval(self, query, owner, rid, fingerprint, conversation):
        key = (owner, rid)
        if key in self.rows:
            return None
        self.rows[key] = dict(request_id=rid, fingerprint=fingerprint,
                              conversation_id=conversation, status="accepted", response=None)
        return rid

    async def fetchrow(self, query, owner, rid):
        return self.rows.get((owner, rid))

    async def execute(self, query, owner, rid, *args):
        row = self.rows[(owner, rid)]
        if "status='completed'" in query:
            row.update(status="completed", response=args[0])
        else:
            row.update(status="uncertain")


@pytest.fixture
def ledger(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_FIRST_PARTY_REQUEST_LEDGER_ENABLED", "1")
    db = LedgerDB()
    @asynccontextmanager
    async def connection():
        yield db
    monkeypatch.setattr(native, "_conversation_db", connection)
    monkeypatch.setattr(native, "_owner", AsyncMock(return_value="owner-a"))
    return db


def test_replay_conflict_and_owner_scope(ledger, monkeypatch):
    async def scenario():
        execution = AsyncMock(return_value={"message": "ok"})
        monkeypatch.setattr(native, "_execute_chat", execution)
        rid = uuid4()
        payload = native.ChatInput(message="hello", request_id=rid)
        first = await native.chat(payload, object())
        assert await native.chat(payload, object()) == first
        assert execution.await_count == 1
        with pytest.raises(HTTPException) as conflict:
            await native.chat(native.ChatInput(message="different", request_id=rid), object())
        assert conflict.value.status_code == 409
        assert (await native.request_status(rid, object()))["response"] == first
        monkeypatch.setattr(native, "_owner", AsyncMock(return_value="owner-b"))
        with pytest.raises(HTTPException) as unknown:
            await native.request_status(rid, object())
        assert unknown.value.status_code == 404
    asyncio.run(scenario())


def test_concurrent_and_uncertain_are_never_reexecuted(ledger, monkeypatch):
    async def scenario():
        entered = asyncio.Event()
        release = asyncio.Event()
        async def execute(*args):
            entered.set()
            await release.wait()
            raise RuntimeError("unknown external outcome")
        invocation = AsyncMock(side_effect=execute)
        monkeypatch.setattr(native, "_execute_chat", invocation)
        rid = uuid4()
        payload = native.ChatInput(message="hello", request_id=rid)
        first = asyncio.create_task(native.chat(payload, object()))
        await entered.wait()
        with pytest.raises(HTTPException) as concurrent:
            await native.chat(payload, object())
        assert concurrent.value.status_code == 409
        release.set()
        with pytest.raises(RuntimeError):
            await first
        assert (await native.request_status(rid, object()))["status"] == "uncertain"
        with pytest.raises(HTTPException) as retry:
            await native.chat(payload, object())
        assert retry.value.status_code == 409
        assert invocation.await_count == 1
    asyncio.run(scenario())
