"""Shared bounded execution semantics for all DragonZpyder agent surfaces.

The graph limit covers middleware supersteps, not inference spending. Model
and tool middleware and the inference gateway retain their independent caps.
Never replay uncertain actions or infer objective success from a checkpoint.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any

GRAPH_SUPERSTEPS = 128
STRESS_GRAPH_SUPERSTEPS = 384
RECOVERY_TIMEOUT_SECONDS = 10
_STRESS_FLAGS = (
    "DRAGONZPYDER_AGENT_HARNESS_V2",
    "DRAGONZPYDER_AGENT_STRESS_EVAL_ENABLED",
    "DRAGONZPYDER_AGENT_EVAL_ALLOW_PAID",
    "DRAGONZPYDER_AGENT_USE_GATEWAY",
    "DRAGONZPYDER_AGENT_PRODUCTION_MODE",
)


@dataclass(frozen=True)
class ExecutionLimits:
    graph_supersteps: int
    deadline_seconds: int


def execution_limits(*, parent_job: bool = False) -> ExecutionLimits:
    stress = all(os.getenv(flag) == "1" for flag in _STRESS_FLAGS)
    if stress:
        return ExecutionLimits(STRESS_GRAPH_SUPERSTEPS, 110 if parent_job else 220)
    return ExecutionLimits(GRAPH_SUPERSTEPS, 90)


def exact_turn_state(values: Any, *, turn_id: str, prompt: str,
                     require_answer: bool) -> dict:
    """Scope evidence to the uniquely identified latest persisted human turn.

    Fail closed if compaction removed the exact turn or a concurrent writer
    advanced the thread. The caller generates the ID; model data never grants
    access. Files remain context, not proof of writes during this turn.
    """
    messages = values.get("messages") if isinstance(values, dict) else None
    if not isinstance(messages, list):
        raise ValueError("Current turn missing")
    positions = [i for i, m in enumerate(messages)
                 if getattr(m, "type", None) == "human"
                 and getattr(m, "id", None) == turn_id
                 and getattr(m, "content", None) == prompt]
    if len(positions) != 1:
        raise ValueError("Current turn not uniquely persisted")
    tail = messages[positions[0]:]
    if any(getattr(m, "type", None) == "human" for m in tail[1:]):
        raise ValueError("Current turn superseded")
    if require_answer:
        last = tail[-1]
        if (getattr(last, "type", None) != "ai"
                or getattr(last, "tool_calls", None)
                or getattr(last, "invalid_tool_calls", None)
                or not getattr(last, "content", None)):
            raise ValueError("No final assistant answer")
    return {**values, "messages": tail}
