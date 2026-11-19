"""Staging-only, read-only Operly business workflow canary.

Runs a small approved business plan using the actual scoped broker adapter.
The short-lived lease stays private to this process; results are reduced to
minimal structured counts/digests rather than logging business records.
This does not create a recurring goal or mint user authorization.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any
from urllib.parse import urlsplit

from .operly_broker import readonly_tools

_OPERATIONS = {
    "daily_operations": (
        ("workspace.summary.read", {}),
        ("workspace.attention.list", {}),
        ("workspace.activity.list", {"limit": 10}),
    ),
    "business_search": (("workspace.search", None),),
    "customer_review": (("workspace.customer.snapshot", None),),
}
_ALLOWED = frozenset(x[0] for rows in _OPERATIONS.values() for x in rows)
_SAFE_ERROR = re.compile(r"^[a-z][a-z0-9_]{0,59}$")
_ID = re.compile(r"^[a-zA-Z0-9_-]{1,80}$")


class BusinessCanaryError(RuntimeError):
    pass


def _gate() -> None:
    if os.getenv("DRAGONZPYDER_OPERLY_BUSINESS_CANARY_ENABLED") != "1" or os.getenv("DRAGONZPYDER_STAGE") != "staging":
        raise BusinessCanaryError("Operly business canary is staging-only and disabled by default")
    # A staging canary may never silently read the public production Operly workspace.
    endpoint = urlsplit(os.getenv("DRAGONZPYDER_OPERLY_BROKER_URL", ""))
    if (endpoint.scheme != "http" or not endpoint.hostname or
            not endpoint.hostname.endswith(".railway.internal") or
            endpoint.path != "/api/internal/agent-tools"):
        raise BusinessCanaryError("Business canary requires approved private staging broker")


def _decode(text: Any) -> dict:
    if not isinstance(text, str) or len(text.encode("utf-8")) > 32_000:
        raise BusinessCanaryError("Broker result is not bounded JSON text")
    try:
        parsed = json.loads(text)
    except (ValueError, TypeError) as exc:
        raise BusinessCanaryError("Invalid broker JSON response") from exc
    if not isinstance(parsed, dict):
        raise BusinessCanaryError("Broker result must be an object")
    return parsed


def _blocked(capability_id: str, code: Any, prior: list[dict]) -> dict:
    safe = code if isinstance(code, str) and _SAFE_ERROR.fullmatch(code) else "broker_unavailable"
    return {
        "status": "blocked",
        "reason": safe,
        "blocked_capability": capability_id,
        "receipts": prior,
        "model_calls": 0,
        "external_mutations": 0,
        "objective_verified": False,
    }


def _plan(template: str, *, query: str | None, contact_id: str | None) -> tuple[tuple[str, dict], ...]:
    if template not in _OPERATIONS:
        raise BusinessCanaryError("Unknown approved business workflow")
    if template == "business_search":
        if not isinstance(query, str) or not 1 <= len(query.strip()) <= 80 or any(ord(c) < 32 for c in query):
            raise BusinessCanaryError("Invalid bounded business search query")
        return (("workspace.search", {"query": query.strip(), "limit": 10}),)
    if template == "customer_review":
        if not isinstance(contact_id, str) or not _ID.fullmatch(contact_id):
            raise BusinessCanaryError("Invalid customer identifier")
        return (("workspace.customer.snapshot", {"contact_id": contact_id}),)
    return _OPERATIONS[template]


async def run_business_canary(*, lease: str, template: str = "daily_operations",
                              query: str | None = None, contact_id: str | None = None) -> dict:
    """Execute deterministic bounded business reads via Operly; no model output is authority.

    Return sanitized digests and cardinalities only. Every call is independently
    authorized by Operly's current membership, lease and capability policy.
    """
    _gate()
    steps = _plan(template, query=query, contact_id=contact_id)
    if not 1 <= len(steps) <= 3 or any(cap not in _ALLOWED for cap, _ in steps):
        raise BusinessCanaryError("The requested plan exceeds reviewed read-only capabilities")
    tools = {tool.name: tool for tool in readonly_tools(lease)}
    if set(tools) != {"operly_discover_capabilities", "operly_read_capability"}:
        raise BusinessCanaryError("Unexpected Operly broker adapter tool set")
    receipts = []
    for capability_id, args in steps:
        # Discover immediately before each call. A revoked or disabled tool must
        # stop this run without trying an alternate elevated capability.
        discovery = _decode(await tools["operly_discover_capabilities"].ainvoke(
            {"query": capability_id}
        ))
        if discovery.get("source") != "operly" or discovery.get("scope_kind") != "workspace":
            return _blocked(capability_id, "unverified_workspace_context", receipts)
        described = discovery.get("tools")
        if not isinstance(described, list):
            return _blocked(capability_id, "invalid_discovery", receipts)
        matches = [
            item for item in described if isinstance(item, dict)
            and item.get("id") == capability_id and item.get("risk") == "read_only"
        ]
        if len(matches) != 1:
            return _blocked(capability_id, "not_authorized_or_readonly", receipts)
        # The client additionally pins exact read-only capability IDs; a
        # malicious provider's risk label cannot widen the permitted plan.
        response = _decode(await tools["operly_read_capability"].ainvoke({
            "capability_id": capability_id, "arguments": args,
        }))
        if response.get("ok") is not True or response.get("capability_id") != capability_id:
            return _blocked(capability_id, response.get("error_code", "invalid_receipt"), receipts)
        result = response.get("result")
        if not isinstance(result, dict):
            return _blocked(capability_id, "invalid_receipt", receipts)
        if capability_id == "workspace.attention.list":
            if not isinstance(result.get("items"), list) or not isinstance(result.get("today"), list):
                return _blocked(capability_id, "invalid_business_response", receipts)
            cardinality = len(result["items"]) + len(result["today"])
        elif capability_id == "workspace.activity.list":
            if not isinstance(result.get("events"), list):
                return _blocked(capability_id, "invalid_business_response", receipts)
            cardinality = len(result["events"])
        elif capability_id == "workspace.search":
            if not isinstance(result.get("items"), list):
                return _blocked(capability_id, "invalid_business_response", receipts)
            cardinality = len(result["items"])
        else:
            cardinality = len(result)
        # SHA proves only that data was observed by the canary, not that the
        # provider performed external state changes (this canary has no writes).
        serialized = json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)
        receipts.append({
            "capability_id": capability_id,
            "result_sha256": hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
            "field_or_item_count": cardinality,
        })
    return {
        "status": "read_cycle_completed",
        "template": template,
        "receipts": receipts,
        "model_calls": 0,
        "external_mutations": 0,
        "objective_verified": False,
        "note": "Broker reads returned valid shapes; no independent external-state oracle was run.",
    }
