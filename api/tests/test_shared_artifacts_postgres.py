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


def test_object_backed_artifacts_atomic_publication_and_owner_isolation(monkeypatch):
    import hashlib
    from agent_platform import artifact_object_store
    dsn=os.environ.get("DRAGONZPYDER_BUDGET_TEST_DSN")
    if not dsn:
        pytest.skip("PostgreSQL integration DSN required")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_ARTIFACTS_ENABLED","1")
    monkeypatch.setenv("DRAGONZPYDER_ARTIFACT_KEY_B64",base64.b64encode(os.urandom(32)).decode())
    monkeypatch.setenv("DRAGONZPYDER_ARTIFACT_STORAGE_BACKEND","s3")
    class ObjectStore:
        def __init__(self):
            self.objects={}
            self.puts=0
            self.reads=0
            self.deletes=0
            self.fail_after_put=False
            self.fail_delete=False
        async def put_new(self,key,data):
            self.puts+=1
            assert key not in self.objects
            self.objects[key]=data
            if self.fail_after_put:
                raise TimeoutError("uncertain upload")
        async def read(self,key,expected_size):
            self.reads+=1
            data=self.objects[key]
            assert len(data)==expected_size
            return data
        async def delete(self,key):
            self.deletes+=1
            if self.fail_delete:
                raise TimeoutError("uncertain delete")
            self.objects.pop(key,None)
    store=ObjectStore()
    monkeypatch.setattr(artifact_object_store,"configured_store",lambda:store)
    async def exercise():
        db=await asyncpg.connect(dsn)
        owner="object-artifacts-"+uuid4().hex
        file_id,run_id=uuid4(),uuid4()
        raw=b"private verified artifact bytes"
        try:
            sql=Path(__file__).resolve().parents[1]/"agent_platform/migrations/20261125_shared_artifacts.sql"
            await db.execute(sql.read_text())
            params=dict(owner=owner,name="report.txt",mime="text/plain",data=raw,
                        direction="generated",run_id=run_id,artifact_id=file_id)
            store.fail_after_put=True
            with pytest.raises(HTTPException) as error:
                await artifacts.put(db,**params)
            assert error.value.status_code==503
            row=await db.fetchrow("SELECT * FROM dz_agent_artifacts WHERE owner_id=$1 AND id=$2",owner,file_id)
            assert row["storage_state"]=="pending" and row["ciphertext"] is None
            assert row["object_key"]==artifact_object_store.object_key(owner,file_id)
            assert raw not in store.objects[row["object_key"]]
            with pytest.raises(HTTPException) as e:
                await artifacts.get(db,owner=owner,file_id=file_id)
            assert e.value.status_code==404
            store.fail_after_put=False
            info=await artifacts.put(db,**params)
            assert store.puts==1 # reconcile existing bytes, do not reissue
            assert info["sha256"]==hashlib.sha256(raw).hexdigest()
            assert (await artifacts.get(db,owner=owner,file_id=file_id))[1]==raw
            reads=store.reads
            with pytest.raises(HTTPException) as e:
                await artifacts.get(db,owner=owner+"-stranger",file_id=file_id)
            assert e.value.status_code==404 and store.reads==reads
            with pytest.raises(HTTPException) as e:
                await artifacts.put(db,**dict(params,data=b"different"))
            assert e.value.status_code==409
            key=row["object_key"]
            original=store.objects[key]
            store.objects[key]=bytes([original[0]^1])+original[1:]
            with pytest.raises(HTTPException) as e:
                await artifacts.get(db,owner=owner,file_id=file_id)
            assert e.value.status_code==503
            store.objects[key]=original
            store.fail_delete=True
            with pytest.raises(HTTPException):
                await artifacts.delete(db,owner=owner,file_id=file_id)
            with pytest.raises(HTTPException) as e:
                await artifacts.get(db,owner=owner,file_id=file_id)
            assert e.value.status_code==404
            store.fail_delete=False
            await artifacts.delete(db,owner=owner,file_id=file_id)
            assert key not in store.objects
            assert await db.fetchval("SELECT storage_state FROM dz_agent_artifacts WHERE owner_id=$1 AND id=$2",owner,file_id)=="deleted"
            with pytest.raises(HTTPException) as e:
                await artifacts.put(db,**params)
            assert e.value.status_code==409 and store.puts==1
        finally:
            await db.execute("DELETE FROM dz_agent_artifacts WHERE owner_id=$1",owner)
            await db.close()
    asyncio.run(exercise())


def test_computer_admission_enforces_atomic_quota_and_revocation(monkeypatch):
    from contextlib import asynccontextmanager
    from agent_platform.computer_admission import admitted_run,ComputerAdmissionPolicy
    dsn=os.environ.get("DRAGONZPYDER_BUDGET_TEST_DSN")
    if not dsn:
        pytest.skip("PostgreSQL integration DSN required")
    owner="computer-"+uuid4().hex
    @asynccontextmanager
    async def db_factory():
        db=await asyncpg.connect(dsn)
        try:
            yield db
        finally:
            await db.close()
    class VM:
        def __init__(self,uncertain=False):
            self.calls=[]
            self.uncertain=uncertain
        async def create(self,**kw):
            self.calls.append("create")
            return {"id":"sandbox-"+uuid4().hex}
        async def execute_authorized(self,**kw):
            self.calls.append("execute")
            return {"ok":True}
        async def destroy_authorized(self,*a,**kw):
            self.calls.append("destroy")
            if self.uncertain:
                raise TimeoutError()
            return {"destroyed":True}
    policy=ComputerAdmissionPolicy("0.01","0.02","0.03",owner_active=1,global_active=3)
    async def exercise():
        allowed=True
        async def authorize():
            if not allowed:
                raise PermissionError("revoked")
        async with db_factory() as db:
            sql=Path(__file__).resolve().parents[1]/"agent_platform/migrations/20261126_computer_admission.sql"
            await db.execute(sql.read_text())
        vm1,vm2=VM(),VM()
        runid1,runid2=uuid4(),uuid4()
        first=admitted_run(db_factory=db_factory,owner=owner,run_id=runid1,
                          policy=policy,transport=vm1,authorize=authorize)
        second=admitted_run(db_factory=db_factory,owner=owner,run_id=runid2,
                           policy=policy,transport=vm2,authorize=authorize)
        try:
            a,b=await asyncio.gather(first.execute("files.list",{}),second.execute("files.list",{}),
                                     return_exceptions=True)
            assert sum(isinstance(x,dict) for x in (a,b))==1
            assert sum(isinstance(x,PermissionError) for x in (a,b))==1
            winning,vm,winning_id=(first,vm1,runid1) if isinstance(a,dict) else (second,vm2,runid2)
            assert vm.calls==["create","execute"]
            allowed=False
            with pytest.raises(PermissionError):
                await winning.execute("files.list",{})
            assert vm.calls==["create","execute"]
            assert await winning.close()
            async with db_factory() as db:
                assert await db.fetchval("SELECT state FROM dz_computer_allocations WHERE run_id=$1",winning_id)=="destroyed"
            allowed=True
            replay=admitted_run(db_factory=db_factory,owner=owner,run_id=winning_id,
                               policy=policy,transport=VM(),authorize=authorize)
            with pytest.raises(PermissionError):
                await replay.execute("files.list",{})
            lost_vm=VM(uncertain=True)
            lost_id=uuid4()
            lost=admitted_run(db_factory=db_factory,owner=owner,run_id=lost_id,
                             policy=policy,transport=lost_vm,authorize=authorize)
            await lost.execute("files.list",{})
            assert not await lost.close()
            async with db_factory() as db:
                assert await db.fetchval("SELECT state FROM dz_computer_allocations WHERE run_id=$1",lost_id)=="uncertain"
            denied_vm=VM()
            denied=admitted_run(db_factory=db_factory,owner=owner,run_id=uuid4(),
                               policy=policy,transport=denied_vm,authorize=authorize)
            with pytest.raises(PermissionError):
                await denied.execute("files.list",{})
            assert denied_vm.calls==[]
        finally:
            await first.close()
            await second.close()
            async with db_factory() as db:
                await db.execute("DELETE FROM dz_computer_allocations WHERE owner_id=$1",owner)
    asyncio.run(exercise())
