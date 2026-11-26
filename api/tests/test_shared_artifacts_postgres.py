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


def test_vm_artifact_roundtrip_real_postgres_and_authenticated_download(monkeypatch):
    from contextlib import asynccontextmanager
    import hashlib
    from agent_platform.computer import ComputerScope
    from agent_platform.computer_run import ComputerRun,ComputerRunGrant
    from agent_platform.computer_artifacts import ComputerArtifacts
    from agent_platform import artifact_http
    dsn=os.environ.get("DRAGONZPYDER_BUDGET_TEST_DSN")
    if not dsn:
        pytest.skip("PostgreSQL integration DSN required")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_ARTIFACTS_ENABLED","1")
    monkeypatch.setenv("DRAGONZPYDER_ARTIFACT_KEY_B64",base64.b64encode(os.urandom(32)).decode())
    owner="artifact-"+uuid4().hex
    run_id=uuid4()
    class VM:
        def __init__(self):
            self.files={}
            self.calls=[]
        async def create(self,**kw):
            return {"id":"vm-test-123"}
        async def execute_authorized(self,*,sandbox_id,scope,tool_id,args):
            self.calls.append(tool_id)
            assert scope.principal_id==owner
            path=args["path"]
            if tool_id=="artifact.import":
                self.files[path]=base64.b64decode(args["content_base64"],validate=True)
            data=self.files[path]
            return {"ok":True,"path":path,"size_bytes":len(data),
                    "sha256":hashlib.sha256(data).hexdigest(),
                    "content_base64":base64.b64encode(data).decode()}
        async def destroy_authorized(self,*a,**kw):
            return {"destroyed":True}
    @asynccontextmanager
    async def db_factory():
        db=await asyncpg.connect(dsn)
        try:
            yield db
        finally:
            await db.close()
    async def exercise():
        vm=VM()
        run=ComputerRun(vm,ComputerRunGrant(ComputerScope("personal",owner,"task-test-123")))
        try:
            async with db_factory() as db:
                sql=Path(__file__).resolve().parents[1]/"agent_platform/migrations/20261125_shared_artifacts.sql"
                await db.execute(sql.read_text())
                inp=await artifacts.put(db,owner=owner,name="input.bin",mime="application/octet-stream",data=b"\x00\xffinput")
            fid=UUID(inp["id"])
            binding=ComputerArtifacts(run=run,db_factory=db_factory,owner=owner,run_id=run_id,allowed_ids=[fid])
            with pytest.raises(ValueError):
                ComputerArtifacts(run=run,db_factory=db_factory,owner="other",run_id=run_id,allowed_ids=[fid])
            with pytest.raises(PermissionError):
                await binding.import_selected(uuid4(),"input.bin")
            assert vm.calls==[]
            imported=await binding.import_selected(fid,"input.bin")
            assert imported["sha256"]==inp["sha256"]
            assert vm.files["input.bin"]==b"\x00\xffinput"
            # Simulated VM operation only; bytes persist in actual PostgreSQL.
            vm.files["result.txt"]=b"verified output\n"
            first=await binding.publish("result.txt","result.txt","text/plain")
            second=await binding.publish("result.txt","result.txt","text/plain")
            assert first==second
            async with db_factory() as db:
                assert await db.fetchval("SELECT count(*) FROM dz_agent_artifacts WHERE owner_id=$1 AND run_id=$2",owner,run_id)==1
            async def auth(request,*,changing):
                return owner
            monkeypatch.setattr(artifact_http,"_owner",auth)
            monkeypatch.setattr(artifact_http,"_conversation_db",db_factory)
            resp=await artifact_http.download(UUID(first["id"]),None)
            assert resp.body==b"verified output\n"
            assert resp.headers["content-disposition"].startswith("attachment;")
            async def stranger(request,*,changing):
                return owner+"-other"
            monkeypatch.setattr(artifact_http,"_owner",stranger)
            with pytest.raises(HTTPException) as denied:
                await artifact_http.download(UUID(first["id"]),None)
            assert denied.value.status_code==404
            # Changed file produces a new immutable version.
            vm.files["result.txt"]=b"updated output\n"
            third=await binding.publish("result.txt","result.txt","text/plain")
            assert third["id"]!=first["id"]
            async with db_factory() as db:
                _,old=await artifacts.get(db,owner=owner,file_id=UUID(first["id"]))
                assert old==b"verified output\n"
        finally:
            await run.close()
            async with db_factory() as db:
                await db.execute("DELETE FROM dz_agent_artifacts WHERE owner_id=$1",owner)
    asyncio.run(exercise())
