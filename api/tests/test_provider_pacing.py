"""Provider rate admission contracts with no paid requests."""
import asyncio
from datetime import datetime, timedelta, timezone
import pytest

from agent_platform.provider_pacing import AgentProviderPacer, retry_after_seconds


@pytest.mark.parametrize(("raw","expected"),[
    ("1",1),("0.2",1),("2.1",3),("60",30),
    ("",None),("-1",None),("NaN",None),("Infinity",None),
    ("untrusted",None),
])
def test_retry_after_sanitized_and_bounded(raw,expected):
    assert retry_after_seconds(raw)==expected


def test_retry_after_http_date():
    now=datetime(2026,11,8,18,0,0,tzinfo=timezone.utc)
    future=(now+timedelta(seconds=11)).strftime("%a, %d %b %Y %H:%M:%S GMT")
    assert retry_after_seconds(future,now=now)==11


def test_admission_concurrency_is_bounded():
    async def scenario():
        pacer=AgentProviderPacer(concurrency=2,spacing_s=0)
        running=0
        max_seen=0
        async def task():
            nonlocal running,max_seen
            async with pacer.slot():
                running+=1
                max_seen=max(max_seen,running)
                await asyncio.sleep(0.01)
                running-=1
        await asyncio.gather(*(task() for _ in range(12)))
        return max_seen
    assert asyncio.run(scenario())==2


def test_cooldown_does_not_block_or_retry_a_provider_call():
    async def scenario():
        pacer=AgentProviderPacer(concurrency=1,spacing_s=0)
        result=await pacer.cooldown("31")
        assert result==30
    asyncio.run(scenario())


@pytest.mark.parametrize("concurrency,spacing",[(-1,0),(0,0),(9,0),(2,-1),(2,6)])
def test_reject_invalid_limits(concurrency,spacing):
    with pytest.raises(ValueError):
        AgentProviderPacer(concurrency=concurrency,spacing_s=spacing)
