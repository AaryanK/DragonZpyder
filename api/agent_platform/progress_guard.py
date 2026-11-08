"""Bound a stuck supervisor by *observed tool actions*, not more paid calls.

LangChain's before_model hook sees checkpointed messages and checks for
identical tool-call cycles. No prompts, tool arguments or fingerprints are
logged, exported, or persisted. Terminations are NEVER benchmark passes.
"""
from __future__ import annotations

import hashlib
import json
import os

from langchain.agents.middleware import before_model
from langchain_core.messages import AIMessage

STOP_PREFIX = "DRAGONZPYDER_INCOMPLETE:"
MAX_NORMAL_TURNS = 10
MAX_STRESS_TURNS = 18


def action_fingerprints(messages: list) -> list[str]:
    observed: list[str] = []
    for message in messages[-80:]:
        if getattr(message, "type", None) != "ai":
            continue
        for call in getattr(message, "tool_calls", []) or []:
            if not isinstance(call, dict):
                continue
            name = call.get("name")
            if not isinstance(name, str) or not name:
                continue
            # All hashes remain local to this decision; never log/hash back
            # out or use them as user-independent replay identifiers.
            arguments = call.get("args", {})
            try:
                packed = json.dumps(arguments, sort_keys=True, separators=(",", ":"), default=str)
            except (TypeError, ValueError):
                continue
            observed.append(hashlib.sha256((name + "\0" + packed).encode()).hexdigest())
    return observed[-24:]


def repeated_action_cycle(actions: list[str]) -> bool:
    # Four identical single actions, or three identical 2- / 3-action
    # cycles. A simple duplicate read alone is not sufficient.
    for width, cycles in ((1, 4), (2, 3), (3, 3)):
        count = width * cycles
        if len(actions) < count:
            continue
        tail = actions[-count:]
        if all(tail[i:i+width] == tail[:width] for i in range(0, count, width)):
            return True
    return False


def stop_reason(messages: list, *, stress_mode: bool) -> str | None:
    actions = action_fingerprints(messages)
    if repeated_action_cycle(actions):
        return "repeated_tool_cycle"
    turns = sum(getattr(msg, "type", None) == "ai" for msg in messages)
    if turns >= (MAX_STRESS_TURNS if stress_mode else MAX_NORMAL_TURNS):
        return "step_budget_exhausted"
    return None


def progress_guard_decision(state: dict) -> dict | None:
    is_stress = (
        os.getenv("DRAGONZPYDER_AGENT_STRESS_EVAL_ENABLED") == "1"
        and os.getenv("DRAGONZPYDER_AGENT_EVAL_ALLOW_PAID") == "1"
        and os.getenv("DRAGONZPYDER_AGENT_USE_GATEWAY") == "1"
    )
    reason = stop_reason(state.get("messages", []), stress_mode=is_stress)
    if reason is None:
        return None
    return {
        "messages": [AIMessage(content=(
            STOP_PREFIX + " " + reason
            + "; task stopped within execution limits. "
            + "Any virtual artifacts are partial and not independently verified."
        ))],
        "jump_to": "end",
    }


@before_model(can_jump_to=["end"])
def stop_repeating_agent(state, runtime):
    return progress_guard_decision(state)
