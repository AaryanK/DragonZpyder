"""No-network contract for one-time exact-request OAuth consent."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from contextlib import asynccontextmanager
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from identity.consent import issue_interaction, consume_interaction, request_hash
from identity.grants import OAuthGrantDenied

REQ = {
    "response_type": "code", "client_id": "operly-web", "redirect_uri": "https://operly.example.test/callback",
    "scope": "openid operly:access", "state": "a" * 48, "code_challenge_method": "S256",
    "code_challenge": "b" * 43, "nonce": "n" * 40,
}
class FakeDB:
    def __init__(self):
        self.row = None
    async def execute(self, sql, *args):
        if sql.startswith("INSERT"):
            self.row = {"subject": args[1], "session_hash": args[2],
                        "request_sha256": args[3], "expires_at": args[4],
                        "consumed_at": None, "digest": args[0]}
            return "INSERT 0 1"
        if sql.startswith("UPDATE"):
            if self.row["digest"] != args[0] or self.row["consumed_at"] is not None:
                return "UPDATE 0"
            self.row["consumed_at"] = datetime.now(timezone.utc)
            return "UPDATE 1"
        raise AssertionError(sql)
    async def fetchrow(self, sql, *args):
        return self.row if self.row is not None and self.row["digest"] == args[0] else None

@pytest.mark.asyncio
async def test_ticket_bound_to_exact_browser_request_and_single_use():
    with patch.dict("os.environ", {"DRAGONZPYDER_IDENTITY_GRANT_HASH_KEY": "c" * 48}):
        db = FakeDB()
        ticket = await issue_interaction(db, subject="canonical-user",
                                         session_secret="s" * 48, request=REQ)
        for invalid in [
            {"ticket": "other" * 10, "subject": "canonical-user",
             "session_secret": "s" * 48, "request": REQ},
            {"ticket": ticket, "subject": "different-user",
             "session_secret": "s" * 48, "request": REQ},
            {"ticket": ticket, "subject": "canonical-user",
             "session_secret": "other" * 10, "request": REQ},
            {"ticket": ticket, "subject": "canonical-user",
             "session_secret": "s" * 48, "request": {**REQ, "scope": "openid offline_access"}},
            {"ticket": ticket, "subject": "canonical-user",
             "session_secret": "s" * 48, "request": {**REQ, "state": "forged" * 8}},
        ]:
            with pytest.raises(OAuthGrantDenied):
                await consume_interaction(db, **invalid)
        await consume_interaction(db, ticket=ticket, subject="canonical-user",
                                  session_secret="s" * 48, request=REQ)
        with pytest.raises(OAuthGrantDenied):
            await consume_interaction(db, ticket=ticket, subject="canonical-user",
                                      session_secret="s" * 48, request=REQ)

@pytest.mark.asyncio
async def test_expired_ticket_fails_closed():
    with patch.dict("os.environ", {"DRAGONZPYDER_IDENTITY_GRANT_HASH_KEY": "d" * 48}):
        db = FakeDB()
        ticket = await issue_interaction(db, subject="user", session_secret="s" * 48, request=REQ)
        db.row["expires_at"] = datetime.now(timezone.utc) - timedelta(seconds=1)
        with pytest.raises(OAuthGrantDenied):
            await consume_interaction(db, ticket=ticket, subject="user",
                                      session_secret="s" * 48, request=REQ)
