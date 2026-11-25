import asyncio
import httpx
import pytest
from agent_platform import first_party_voice as voice

def test_audio_only_offer():
    audio="v=0\r\nm=audio 9 UDP/TLS/RTP/SAVPF 111\r\n"
    assert voice._audio_offer(audio)
    assert not voice._audio_offer(audio+"m=video 9 UDP/TLS/RTP/SAVPF 96\r\n")
    assert not voice._audio_offer(audio+"\x00")
    assert not voice._audio_offer(audio+"x"*65536)

def test_provider_location_never_becomes_arbitrary_url():
    assert voice._call_id("/v1/realtime/calls/rtc_1")=="rtc_1"
    assert voice._call_id("https://api.openai.com/v1/realtime/calls/rtc_1")=="rtc_1"
    for location in ["https://evil.invalid/v1/realtime/calls/rtc_1","/v1/realtime/calls/../key","/v1/realtime/calls/rtc_1?x=1"]:
        with pytest.raises(ValueError):
            voice._call_id(location)

def test_voice_requires_explicit_flag_and_dedicated_key(monkeypatch):
    monkeypatch.delenv("DRAGONZPYDER_NATIVE_VOICE_API_KEY",raising=False)
    monkeypatch.setenv("DRAGONZPYDER_NATIVE_VOICE_ENABLED","1")
    assert not voice.voice_enabled()
    monkeypatch.setenv("DRAGONZPYDER_NATIVE_VOICE_API_KEY","test-only")
    assert voice.voice_enabled()
    monkeypatch.setenv("DRAGONZPYDER_NATIVE_VOICE_ENABLED","0")
    assert not voice.voice_enabled()

def test_hangup_uses_fixed_provider_and_idempotent_not_found():
    requests=[]
    def handle(request):
        requests.append(request)
        return httpx.Response(404)
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            assert await voice._hangup(client,"test-only","rtc_1")
            assert not await voice._hangup(client,"test-only","../bad")
    asyncio.run(run())
    assert len(requests)==1
    assert str(requests[0].url)=="https://api.openai.com/v1/realtime/calls/rtc_1/hangup"
