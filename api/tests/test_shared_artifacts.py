import base64
from io import BytesIO
import os

import pytest
from fastapi import HTTPException

from agent_platform import artifacts
from agent_platform.artifact_formats import render_document


def test_cipher_requires_explicit_gate_and_valid_key(monkeypatch):
    monkeypatch.delenv("DRAGONZPYDER_AGENT_ARTIFACTS_ENABLED",raising=False)
    with pytest.raises(HTTPException) as error:
        artifacts.cipher()
    assert error.value.status_code==503
    monkeypatch.setenv("DRAGONZPYDER_AGENT_ARTIFACTS_ENABLED","1")
    monkeypatch.setenv("DRAGONZPYDER_ARTIFACT_KEY_B64",base64.b64encode(os.urandom(32)).decode())
    enc=artifacts.cipher()
    nonce=os.urandom(12)
    raw=b"Private uploaded data"
    sealed=enc.encrypt(nonce,raw,b"owner-A")
    assert raw not in sealed and enc.decrypt(nonce,sealed,b"owner-A")==raw
    with pytest.raises(Exception):
        enc.decrypt(nonce,sealed,b"owner-B")


@pytest.mark.parametrize("value",["../bad","a/b","a\\b","a\r\nheader",".","..","\u202e.exe"])
def test_reject_unsafe_names(value):
    with pytest.raises(HTTPException):
        artifacts.filename(value)


def test_real_office_and_pdf_output():
    from pypdf import PdfReader
    from docx import Document
    from openpyxl import load_workbook
    from pptx import Presentation
    spec={"title":"Test report","paragraphs":["Evidence and results"]}
    pdf=render_document("pdf",spec)
    assert pdf.startswith(b"%PDF") and "Evidence" in PdfReader(BytesIO(pdf)).pages[0].extract_text()
    assert Document(BytesIO(render_document("docx",spec))).paragraphs[1].text=="Evidence and results"
    sheet=load_workbook(BytesIO(render_document("xlsx",{"rows":[["name","value"],["=1+1",4]]})))
    assert sheet.active["A2"].data_type=="s" and sheet.active["B2"].value==4
    deck=Presentation(BytesIO(render_document("pptx",{"slides":[{"title":"Evidence","bullets":["Verified output"]}]})))
    assert len(deck.slides)==1 and deck.slides[0].shapes.title.text=="Evidence"


def test_s3_object_store_uses_conditional_put_bounded_read_and_private_keys():
    import asyncio
    from uuid import uuid4
    from agent_platform.artifact_object_store import S3ArtifactStore,object_key
    fid=uuid4()
    key=object_key("sensitive-owner",fid)
    assert "sensitive-owner" not in key
    assert key!=object_key("other-owner",fid)
    class S3:
        objects={}
        def put_object(self,**args):
            assert args["Bucket"]=="private-artifacts"
            assert args["IfNoneMatch"]=="*" and "ACL" not in args
            self.objects[args["Key"]]=args["Body"]
        def get_object(self,**args):
            data=self.objects[args["Key"]]
            return {"ContentLength":len(data),"Body":BytesIO(data)}
        def delete_object(self,**args):
            self.objects.pop(args["Key"],None)
    async def run():
        s=S3ArtifactStore(S3(),"private-artifacts")
        data=b"x"*32
        await s.put_new(key,data)
        assert await s.read(key,32)==data
        with pytest.raises(ValueError):
            await s.read(key,31)
        await s.delete(key)
    asyncio.run(run())
