"""LangGraph-native bounded parallel investigation (staging opt-in).

Each child gets an isolated track and returns only a bounded sanitized report.
This graph performs no external tool actions on its own. Real model tracks
must be invoked through an approved metered AgentRuntime worker.
"""
from __future__ import annotations

import asyncio
import math
import operator
import re
from time import monotonic_ns
from typing import Annotated, Awaitable, Callable, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

_ID = re.compile(r"^[A-Za-z0-9_-]{1,24}$")
MAX_TRACKS = 3
MAX_PROMPT_CHARS = 11000
DEFAULT_TRACK_TIMEOUT_S = 180.0
MAX_TRACK_TIMEOUT_S = 240.0


class ParallelState(TypedDict, total=False):
    tracks: list[dict]
    track: dict
    results: Annotated[list[dict], operator.add]


def validate_tracks(tracks: list[dict]) -> None:
    if not isinstance(tracks, list) or not 2 <= len(tracks) <= MAX_TRACKS:
        raise ValueError("Parallel workflow requires two or three tracks")
    seen: set[str] = set()
    for track in tracks:
        if not isinstance(track, dict) or set(track) != {"id", "prompt"}:
            raise ValueError("Each track requires only id and prompt")
        tid, prompt = track["id"], track["prompt"]
        if not isinstance(tid, str) or not _ID.fullmatch(tid) or tid in seen:
            raise ValueError("Invalid or duplicate track ID")
        if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= MAX_PROMPT_CHARS:
            raise ValueError("Invalid track prompt")
        seen.add(tid)


def _valid_timeout(seconds: float) -> float:
    if type(seconds) not in (int, float) or not math.isfinite(seconds):
        raise ValueError("Invalid parallel track deadline")
    if not 0.001 <= seconds <= MAX_TRACK_TIMEOUT_S:
        raise ValueError("Parallel track deadline must be bounded")
    return float(seconds)


def build_parallel_graph(
    worker: Callable[[dict], Awaitable[dict]], *,
    track_timeout_s: float = DEFAULT_TRACK_TIMEOUT_S,
):
    """Explicit Send fan-out, bounded fan-in and isolated failures."""
    track_timeout_s = _valid_timeout(track_timeout_s)
    start_ns = monotonic_ns()

    async def investigate(state: ParallelState) -> dict:
        track = state["track"]
        begun = monotonic_ns()
        try:
            response = await asyncio.wait_for(worker(track), timeout=track_timeout_s)
            if not isinstance(response, dict) or not isinstance(response.get("answer"), str):
                raise ValueError("Worker did not return an answer report")
            # User-facing model prose is untrusted and cannot claim an outcome pass.
            answer = response["answer"][:16000]
            outcome = response.get("status", "completed")
            data = {
                "id": track["id"],
                "status": "incomplete" if outcome == "incomplete" else "reported",
                "answer": answer,
                "truncated": len(response["answer"]) > 16000,
                "artifact_paths": [
                    x for x in (response.get("virtual_artifact_paths") or [])[:30]
                    if isinstance(x, str) and x.startswith("/workspace/")
                ],
                "tool_names": [
                    x for x in (response.get("successful_tools") or [])[:80]
                    if isinstance(x, str)
                ],
                "objective_verified": False,
                "termination_reason": (
                    response.get("termination_reason")
                    if outcome == "incomplete" and isinstance(
                        response.get("termination_reason"), str
                    ) else None
                ),
                "checkpoint_recovered": bool(response.get("checkpoint_recovered")),
            }
        except Exception as exc:
            # Never leak provider exception text, which can contain credentials.
            data = {
                "id": track["id"], "status": "failed",
                "failure_type": type(exc).__name__,
                "objective_verified": False,
            }
        ended = monotonic_ns()
        data.update({
            "start_ms": round((begun - start_ns) / 1_000_000, 3),
            "end_ms": round((ended - start_ns) / 1_000_000, 3),
        })
        return {"results": [data]}

    def dispatch(state: ParallelState):
        return [Send("investigate", {"track": t}) for t in state["tracks"]]

    graph = StateGraph(ParallelState)
    graph.add_node("investigate", investigate)
    graph.add_conditional_edges(START, dispatch, ["investigate"])
    graph.add_edge("investigate", END)
    return graph.compile()


async def run_parallel_tracks(
    tracks: list[dict], worker: Callable[[dict], Awaitable[dict]], *,
    track_timeout_s: float = DEFAULT_TRACK_TIMEOUT_S,
) -> dict:
    validate_tracks(tracks)
    graph = build_parallel_graph(worker, track_timeout_s=track_timeout_s)
    state = await graph.ainvoke({"tracks": tracks, "results": []})
    results = sorted(state["results"], key=lambda row: row["id"])
    completed = [r for r in results if r["status"] == "reported"]
    overlap = any(
        a["id"] != b["id"] and
        max(a["start_ms"], b["start_ms"]) < min(a["end_ms"], b["end_ms"])
        for i, a in enumerate(completed) for b in completed[i + 1:]
    )
    return {
        "tracks": results,
        "completed": len(completed),
        "failed": len(results) - len(completed),
        "parallelism_observed": overlap,
        "objective_verified": False,
        "note": "Concurrent model runs and generated artifacts need independent validation.",
    }
