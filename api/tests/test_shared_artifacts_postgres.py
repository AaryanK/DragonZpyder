import asyncio
import base64
import os
from pathlib import Path
from uuid import UUID, uuid4

import asyncpg
import pytest
from fastapi import HTTPException
from agent_platform import artifacts


def test_binary_storage_encryption_and_owner_isolation(monkeypatch):
    dsn=os.environ.get("DRAGONZPYDER_BUDGET_TEST_DSN")
    if not dsn:
        pytest.skip("PostgreSQL integration DSN required")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_ARTIFACTS_ENABLED","1")
    monkeypatch.setenv("DRAGONZPYDER_ARTIFACT_KEY_B64",base64.b64encode(os.urandom(32)).decode())
    async def exercise():
        db=await asyncpg.connect(dsn)
        owner="artifacts-test-"+str(uuid4())
        stranger=owner+"-other"
        data=b"\x00\xff Arbitrary binary attachment"
        try:
            sql=Path(__file__).resolve().parents[1]/"agent_platform/migrations/20261125_shared_artifacts.sql"
            await db.execute(sql.read_text())
            info=await artifacts.put(db,owner=owner,name="example.bin",mime="application/octet-stream",data=data)
            file_id=UUID(info["id"])
            row=await db.fetchrow("SELECT ciphertext,nonce FROM dz_agent_artifacts WHERE owner_id=$1 AND id=$2",owner,file_id)
            assert data not in bytes(row["ciphertext"])
            assert len(row["nonce"])==12
            received,raw=await artifacts.get(db,owner=owner,file_id=file_id)
            assert raw==data and received==info
            with pytest.raises(HTTPException) as exc:
                await artifacts.get(db,owner=stranger,file_id=file_id)
            assert exc.value.status_code==404
            with pytest.raises(HTTPException) as exc:
                await artifacts.describe(db,owner=stranger,ids=[file_id])
            assert exc.value.status_code==404
            await db.execute("UPDATE dz_agent_artifacts SET filename='tampered.bin' WHERE owner_id=$1 AND id=$2",owner,file_id)
            with pytest.raises(HTTPException) as exc:
                await artifacts.get(db,owner=owner,file_id=file_id)
            assert exc.value.status_code==503
        finally:
            await db.execute("DELETE FROM dz_agent_artifacts WHERE owner_id=$1",owner)
            await db.close()
    asyncio.run(exercise())
