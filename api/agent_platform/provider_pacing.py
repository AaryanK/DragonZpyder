"""Gateway-local paced admission and safe rate-limit hints for agent inference.

This reduces provider burst 429s, but is NOT cross-replica rate accounting
or an atomic USD spend budget. No silent retries after ambiguous outcomes.
"""
from __future__ import annotations
import asyncio
import math
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime


def retry_after_seconds(raw: str | None, *, now: datetime | None = None) -> int | None:
    """Parse provider Retry-After delta or RFC-compliant HTTP date, capped."""
    if not isinstance(raw,str) or not 1<=len(raw)<=96:
        return None
    try:
        value=float(raw)
        if not math.isfinite(value) or value<0:
            return None
        return min(30,max(1,math.ceil(value)))
    except ValueError:
        pass
    try:
        date=parsedate_to_datetime(raw)
        if date.tzinfo is None:
            return None
        now=now or datetime.now(timezone.utc)
        delta=(date-now).total_seconds()
        if not math.isfinite(delta) or delta<=0:
            return None
        return min(30,max(1,math.ceil(delta)))
    except (ValueError,TypeError,OverflowError,IndexError):
        return None


class AgentProviderPacer:
    """Local bounded concurrency and spacing, no payment retries."""
    def __init__(self, *, concurrency: int=2, spacing_s: float=0.4):
        if not isinstance(concurrency,int) or not 1<=concurrency<=8:
            raise ValueError("Concurrency out of bounds")
        if not isinstance(spacing_s,(int,float)) or not 0<=spacing_s<=5:
            raise ValueError("Spacing out of bounds")
        self._slots=asyncio.Semaphore(concurrency)
        self._lock=asyncio.Lock()
        self._spacing=float(spacing_s)
        self._next_at=0.0

    @asynccontextmanager
    async def slot(self):
        async with self._slots:
            async with self._lock:
                now=time.monotonic()
                sleep_for=max(0.0,self._next_at-now)
                self._next_at=max(self._next_at,now)+self._spacing
            if sleep_for:
                await asyncio.sleep(sleep_for)
            yield

    async def cooldown(self, retry_after: str | None) -> int:
        seconds=retry_after_seconds(retry_after) or 2
        async with self._lock:
            self._next_at=max(self._next_at,time.monotonic()+seconds)
        return seconds
