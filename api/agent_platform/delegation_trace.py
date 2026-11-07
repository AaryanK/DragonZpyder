"""Privacy-minimal evidence of Deep Agents task-tool delegation.

Records only tool run IDs, relative timestamps and success/failure. It never
stores prompts, tool arguments, outputs, model messages, secrets or raw traces.
A tool callback establishes *observed invocation*, not verified objective work.
"""
from __future__ import annotations

from hashlib import sha256
from threading import Lock
from time import monotonic_ns
from typing import Callable

from langchain_core.callbacks import BaseCallbackHandler


class DelegationTrace(BaseCallbackHandler):
    """LangChain callback for measured overlap of `task` subagent calls."""

    def __init__(self, clock: Callable[[], int] = monotonic_ns):
        super().__init__()
        self._clock = clock
        self._origin = clock()
        self._lock = Lock()
        self._active: dict[str, int] = {}
        self._finished: list[tuple[str, int, int, str]] = []

    def on_tool_start(self, serialized: dict, input_str: str, *,
                      run_id, **kwargs) -> None:
        # The input string can include user content; NEVER record it.
        name = (serialized or {}).get("name") or kwargs.get("name")
        if name != "task":
            return
        with self._lock:
            self._active[str(run_id)] = self._clock()

    def _finish(self, run_id, status: str) -> None:
        with self._lock:
            started = self._active.pop(str(run_id), None)
            if started is not None:
                self._finished.append((str(run_id), started, self._clock(), status))

    def on_tool_end(self, output, *, run_id, **kwargs) -> None:
        self._finish(run_id, "completed")

    def on_tool_error(self, error, *, run_id, **kwargs) -> None:
        self._finish(run_id, "failed")

    def snapshot(self) -> dict:
        """Completed spans only. Incomplete callbacks never count as successes."""
        with self._lock:
            rows = sorted(self._finished, key=lambda x: (x[1], x[0]))[:20]
            still_active = len(self._active)
        spans = []
        for run_id, begin, end, status in rows:
            if end <= begin:
                continue
            spans.append({
                "agent": sha256(run_id.encode("utf-8")).hexdigest()[:16],
                "start_ms": round((begin - self._origin) / 1_000_000, 3),
                "end_ms": round((end - self._origin) / 1_000_000, 3),
                "status": status,
            })
        successful = [s for s in spans if s["status"] == "completed"]
        concurrent = any(
            a["agent"] != b["agent"]
            and max(a["start_ms"], b["start_ms"]) < min(a["end_ms"], b["end_ms"])
            for i, a in enumerate(successful) for b in successful[i + 1:]
        )
        return {
            "spans": spans,
            "parallelism_observed": concurrent,
            "delegated_calls_observed": len(spans),
            "unfinished_calls": still_active,
            "note": "Tool timings do not by themselves prove independent results.",
        }
