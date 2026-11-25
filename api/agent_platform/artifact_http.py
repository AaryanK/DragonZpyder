"""First-party HTTP adapter for shared encrypted files."""
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from . import artifacts
from .first_party_chat import _owner, _conversation_db

router=APIRouter(prefix="/v2/personal/files",tags=["agent-artifacts"])


@router.post("")
async def upload(request: Request, filename: str):
    owner=await _owner(request,changing=True)
    artifacts.cipher()
    name=artifacts.filename(filename)
    content=bytearray()
    async for chunk in request.stream():
        if len(content)+len(chunk)>artifacts.MAX_BYTES:
            raise HTTPException(413,"Attachment exceeds 10 MiB")
        content.extend(chunk)
    async with _conversation_db() as db:
        return await artifacts.put(db,owner=owner,name=name,mime=request.headers.get("content-type",""),data=bytes(content))


@router.get("/{file_id}")
async def download(file_id: UUID,request: Request):
    owner=await _owner(request,changing=False)
    async with _conversation_db() as db:
        info,data=await artifacts.get(db,owner=owner,file_id=file_id)
    # Never render uploaded HTML, SVG, or arbitrary active content inline.
    return Response(data,media_type="application/octet-stream",headers={
        "Content-Disposition":"attachment; filename*=UTF-8''"+quote(info["filename"],safe=""),
        "Cache-Control":"private, no-store","X-Content-Type-Options":"nosniff",
        "Content-Security-Policy":"default-src 'none'; sandbox"})


@router.delete("/{file_id}")
async def delete(file_id: UUID,request: Request):
    owner=await _owner(request,changing=True)
    artifacts.cipher()
    async with _conversation_db() as db:
        row=await db.fetchval("DELETE FROM dz_agent_artifacts WHERE owner_id=$1 AND id=$2 RETURNING id",owner,file_id)
    if row is None:
        raise HTTPException(404,"Artifact not found")
    return {"deleted":str(file_id)}
