"""Conservative classification of observed tool responses.

A successful protocol return is not objective verification. Only trusted
tool-message status and structured top-level envelopes affect this policy;
business records nested in result/data are not interpreted as control signals.
No model prose, provider error strings or credentials are logged.
"""
from __future__ import annotations

import json
from typing import Any

APPROVAL = frozenset({"approval_required", "waiting_for_approval", "pending_approval"})
FAILURE = frozenset({"error", "failed", "denied", "blocked", "cancelled", "timeout"})
UNKNOWN = frozenset({"unknown", "uncertain", "outcome_unknown", "outcome_unconfirmed"})


def _structured_outcome(value: Any, depth: int = 0) -> str:
    if depth > 6:
        return "unknown"
    if isinstance(value, str):
        # Parse only structured JSON, never natural-language instructions.
        if len(value) > 100_000 or value.lstrip()[:1] not in ("{", "["):
            return "returned"
        try:
            return _structured_outcome(json.loads(value), depth + 1)
        except (ValueError, RecursionError):
            return "returned"
    if isinstance(value, list):
        # MCP text-block envelopes, not arbitrary arrays of business records.
        states = [_structured_outcome(item.get("text"), depth + 1)
                  for item in value[:100] if isinstance(item, dict)
                  and item.get("type") == "text"]
        return _combine(states)
    if not isinstance(value, dict):
        return "returned"
    status = value.get("status")
    code = value.get("error_code", value.get("code"))
    tokens = {x for x in (status, code) if isinstance(x, str)}
    if (tokens & APPROVAL or value.get("approval_required") is True
            or value.get("waiting_for_approval") is True):
        return "approval_required"
    if tokens & UNKNOWN:
        return "unknown"
    if (tokens & FAILURE or value.get("isError") is True
            or value.get("ok") is False):
        return "failed"
    states = []
    for key in ("structured_content", "structuredContent"):
        if key in value:
            states.append(_structured_outcome(value[key], depth + 1))
    if isinstance(value.get("content"), list):
        states.append(_structured_outcome(value["content"], depth + 1))
    return _combine(states)


def _combine(states) -> str:
    for state in ("approval_required", "unknown", "failed"):
        if state in states:
            return state
    return "returned"


def tool_outcome(message: Any) -> str:
    """Classify actual tool messages; no arbitrary model-created text accepted."""
    if getattr(message, "type", None) != "tool":
        return "unknown"
    name = getattr(message, "name", None)
    status = getattr(message, "status", None)
    if not isinstance(name, str) or not name:
        return "unknown"
    # Native filesystem and compute tools have their own schemas. Restrict
    # structured business-envelope detection to known broker/capability tools.
    structured = (name.startswith("operly_")
                  or name in {"invoke_tool", "search_tools", "describe_tool"})
    if structured:
        states = [_structured_outcome(getattr(message, "content", None)),
                  _structured_outcome(getattr(message, "artifact", None))]
        if status == "error":
            states.append("failed")
        result = _combine(states)
        if result != "returned":
            return result
    return "returned" if status == "success" else ("failed" if status == "error" else "unknown")


def unresolved_external_control(messages: list) -> str | None:
    """Stop before the next model call if an external action needs intervention.

    This does not undo or prevent other operations in the same dispatched tool
    batch. It is a bounded post-observation guard, not an authorization system.
    """
    # The guard is scoped by the caller to the current human turn.
    for message in messages:
        name = getattr(message, "name", None)
        if (getattr(message, "type", None) != "tool"
                or not isinstance(name, str)
                or not (name.startswith("operly_") or name == "invoke_tool")):
            continue
        outcome = tool_outcome(message)
        if outcome == "approval_required":
            return "external_approval_required"
        if outcome == "unknown":
            return "external_outcome_unconfirmed"
    return None
