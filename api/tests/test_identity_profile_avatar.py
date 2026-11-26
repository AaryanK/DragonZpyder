"""Offline avatar security contracts: exact host, bounds, owner linkage, no redirects."""
import sys
from pathlib import Path
import httpx
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from identity.profile_avatar import verified_avatar_url, fetch_google_avatar, save_google_avatar, read_google_avatar, MAX_AVATAR_BYTES
from identity.providers import ProviderProof

URL = "https://lh3.googleusercontent.com/a/opaque=s96-c"

@pytest.mark.parametrize("bad", ["http://lh3.googleusercontent.com/a/x",
 "https://lh3.googleusercontent.com.evil.test/a/x",
 "https://lh3.googleusercontent.com@evil.test/a/x",
 "https://lh3.googleusercontent.com:443/a/x",
 "https://lh3.googleusercontent.com/a/../x",
 "https://lh3.googleusercontent.com/a/x?next=bad",
 "https://lh3.googleusercontent.com/a/x#fragment",
 "https://127.0.0.1/a/x",
 "https://lh3.googleusercontent.com/a/%2e%2e/x"])
def test_avatar_rejects_untrusted_url(bad):
    assert verified_avatar_url(URL) == URL
    assert verified_avatar_url(bad) is None

@pytest.mark.asyncio
async def test_avatar_no_redirect_or_invalid_image():
    def handler(req):
        assert req.url.host == "lh3.googleusercontent.com"
        assert "authorization" not in req.headers and "cookie" not in req.headers
        return httpx.Response(302, headers={"location":"http://169.254.169.254/"})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert await fetch_google_avatar(client, URL) is None
    for mime, data in [("image/svg+xml", b"<svg/>"), ("image/png", b"not-png"),
                       ("image/jpeg", b"\xff\xd8\xff"+b"x"*MAX_AVATAR_BYTES)]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200,headers={"content-type":mime},content=data))) as client:
            assert await fetch_google_avatar(client,URL) is None

@pytest.mark.asyncio
async def test_avatar_bounded_verified_image():
    data=b"\x89PNG\r\n\x1a\n"+b"x"*20
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,headers={"content-type":"image/png"},content=data))) as client:
        assert await fetch_google_avatar(client, URL)==("image/png",data)

@pytest.mark.asyncio
async def test_avatar_storage_requires_feature_and_google_link(monkeypatch):
    class DB:
        def __init__(self): self.calls=[]
        async def execute(self,sql,*args): self.calls.append((sql,args))
        async def fetchval(self,sql,*args):
            self.calls.append((sql,args))
            return URL
    db=DB()
    proof=ProviderProof("google","verified-provider",profile_picture=URL)
    monkeypatch.delenv("DRAGONZPYDER_IDENTITY_PROFILE_AVATAR_ENABLED",raising=False)
    await save_google_avatar(db,"owner",proof)
    assert await read_google_avatar(db,"owner") is None and db.calls==[]
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_PROFILE_AVATAR_ENABLED","1")
    await save_google_avatar(db,"owner",ProviderProof("discord","discord-id"))
    assert db.calls==[]
    await save_google_avatar(db,"owner",proof)
    assert db.calls[0][1]==(URL,"owner","verified-provider")
    assert "p.login_eligible=TRUE" in db.calls[0][0] and "p.provider_subject=$3" in db.calls[0][0]
    assert await read_google_avatar(db,"owner")==URL
    assert db.calls[-1][1]==("owner",)
