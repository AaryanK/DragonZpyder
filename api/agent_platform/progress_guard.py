"""Bound a stuck supervisor by *observed tool actions*, not more paid calls.

LangChain's before_model hook sees checkpointed messages and checks for
identical tool-call cycles. No prompts, tool arguments or fingerprints are
logged, exported, or persisted. Terminations are NEVER benchmark passes.
"""
from __future__ import annotations

import hashlib
import json
import os

from langchain.agents.middleware import before_model, wrap_model_call
from langchain_core.messages import AIMessage

STOP_PREFIX = "DRAGONZPYDER_INCOMPLETE:"
MAX_NORMAL_TURNS = 16
MAX_STRESS_TURNS = 24


def current_turn_messages(messages: list) -> list:
    """Only messages after the most recent HumanMessage belong to this turn.

    LangGraph checkpoints keep prior completed turns. Their model calls and
    tool actions must not consume the new request's independent run budget.
    For internal/unit states without a HumanMessage, retain original behavior.
    """
    if not isinstance(messages, list):
        return []
    for idx in range(len(messages) - 1, -1, -1):
        if getattr(messages[idx], "type", None) == "human":
            return messages[idx:]
    return messages


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


def stagnant_action_fingerprints(messages: list) -> list[str]:
    """Include observable tool results when detecting repeated cycles.

    Repeated reads whose outputs actually change may be legitimate progress.
    Missing receipts still count as the original action; do not use timestamps
    or callback IDs as evidence of progress. Digests never leave this hook.
    """
    observed = []
    receipts = {
        getattr(message, "tool_call_id", None): message
        for message in messages[-80:]
        if getattr(message, "type", None) == "tool"
        and isinstance(getattr(message, "tool_call_id", None), str)
    }
    for message in messages[-80:]:
        if getattr(message, "type", None) != "ai":
            continue
        for call in getattr(message, "tool_calls", []) or []:
            if not isinstance(call, dict) or not isinstance(call.get("name"), str):
                continue
            response = receipts.get(call.get("id"))
            value = {"name": call["name"], "args": call.get("args", {})}
            if response is not None:
                # Compare only content, not per-call metadata or volatile
                # artifact handles. All computation is local and bounded.
                content = getattr(response, "content", None)
                if isinstance(content, str) and len(content) > 65536:
                    content = content[:32768] + content[-32768:]
                value["observation"] = {
                    "status": getattr(response, "status", None),
                    "content": content,
                }
            try:
                packed = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
                observed.append(hashlib.sha256(packed.encode()).hexdigest())
            except (ValueError, TypeError, RecursionError):
                continue
    return observed[-24:]


def stop_reason(messages: list, *, stress_mode: bool) -> str | None:
    messages = current_turn_messages(messages)
    from .tool_outcomes import unresolved_external_control
    blocker = unresolved_external_control(messages)
    if blocker:
        return blocker
    actions = stagnant_action_fingerprints(messages)
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
    explanation = {
        "external_approval_required": "Review the pending action in the approval interface. No approval or completion is asserted.",
        "external_outcome_unconfirmed": "An external operation has an uncertain outcome. Reconcile its status before retrying.",
    }.get(reason, "Task stopped within execution limits. Any virtual artifacts are partial and not independently verified.")
    return {
        "messages": [AIMessage(content=(
            STOP_PREFIX + " " + reason + "; " + explanation
        ))],
        "jump_to": "end",
    }


@before_model(can_jump_to=["end"])
def stop_repeating_agent(state, runtime):
    return progress_guard_decision(state)



MAX_SPECIALIST_TURNS = 7


def specialist_progress_decision(state: dict) -> dict | None:
    """Terminate a subagent before it consumes the full recursion budget.

    A short specialist should return useful evidence, not recursively ask
    the same questions or chain long independent sub-tasks.
    """
    messages=state.get("messages",[])
    actions=action_fingerprints(messages)
    if repeated_action_cycle(actions):
        reason="specialist_repeated_tool_cycle"
    elif sum(getattr(msg,"type",None)=="ai" for msg in messages)>=MAX_SPECIALIST_TURNS:
        reason="specialist_step_budget_exhausted"
    else:
        return None
    return {
        "messages":[AIMessage(content=(
            STOP_PREFIX+" "+reason+
            "; delegated task incomplete. Evidence requires independent checks."
        ))],
        "jump_to":"end",
    }


@before_model(can_jump_to=["end"])
def stop_repeating_specialist(state, runtime):
    return specialist_progress_decision(state)


def bounded_finalization(limit: int):
    """Reserve the last model call for synthesis; repair one rejected model batch.

    A typed gateway rejection proves no tool in that response was dispatched.
    A model-only retry is still metered and cannot call any tool. Never retry
    generic 502s, timeouts, authorization failures, or uncertain tool effects.
    """
    repaired = False

    @wrap_model_call
    async def finalize_or_repair(request, handler):
        nonlocal repaired
        turns = sum(getattr(m, "type", None) == "ai" for m in
                    current_turn_messages(request.state.get("messages", [])))
        if turns >= limit - 1 and request.tools:
            request = request.override(tool_choice="none")
        try:
            return await handler(request)
        except Exception as exc:
            from .personal_bridge import inference_failure_code
            if (repaired or not request.tools or turns >= limit - 1 or
                    inference_failure_code(exc) != "INFERENCE_TOOL_SELECTION_REJECTED"):
                raise
            repaired = True
            # No side-effect replay. The original batch was rejected before
            # graph dispatch; force a text-only synthesis from existing state.
            return await handler(request.override(tool_choice="none"))
    return finalize_or_repair
