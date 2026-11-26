import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
from fastapi import HTTPException
from agent_platform import first_party_chat as native


def test_goal_management_cannot_cross_owner_or_cancel_inflight(monkeypatch):
    goal = uuid4()
    monkeypatch.setenv("DRAGONZPYDER_FIRST_PARTY_GOAL_MANAGEMENT_ENABLED", "1")
    monkeypatch.setattr(native, "_owner", AsyncMock(return_value="owner-a"))
    class DB:
        state = "inflight"
        async def fetchrow(self, sql, user, gid):
            assert user == "owner-a" and gid == str(goal)
            assert "user_id=$1" in sql
            if "UPDATE" in sql:
                assert "state IN ('preparing','active')" in sql
                if self.state == "active":
                    self.state = "cancelled"
                    return {"state": self.state}
                return None
            if self.state is None:
                return None
            return {"state": self.state}
    db = DB()
    @asynccontextmanager
    async def connection():
        yield db
    monkeypatch.setattr(native, "_conversation_db", connection)
    async def scenario():
        with pytest.raises(HTTPException) as running:
            await native.cancel_goal(goal, object())
        assert running.value.status_code == 409
        db.state = None
        with pytest.raises(HTTPException) as unknown:
            await native.cancel_goal(goal, object())
        assert unknown.value.status_code == 404
        db.state = "active"
        assert (await native.cancel_goal(goal, object()))["state"] == "cancelled"
        assert (await native.cancel_goal(goal, object()))["state"] == "cancelled"
    asyncio.run(scenario())
