from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

JSONValue = None | bool | int | float | str | list["JSONValue"] | dict[str, "JSONValue"]


class CapabilityRisk(StrEnum):
    READ_ONLY = "read_only"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AuthorizationDecision(StrEnum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


class RuntimeStage(StrEnum):
    UNDERSTAND = "understand"
    CLASSIFY = "classify"
    RESOLVE_SCOPE = "resolve_scope"
    RESOLVE_CAPABILITIES = "resolve_authorized_capabilities"
    LOAD_CONTEXT = "load_minimum_context"
    EXPOSE_TOOLS = "expose_allowed_tools"
    REASON_PLAN = "reason_and_plan"
    AUTHORIZE = "authorize"
    EXECUTE = "execute"
    VALIDATE = "validate_result"
    RECORD_TRACE = "record_and_trace"
    EMIT_EVENTS = "emit_events"
    RESPOND = "respond_or_continue"


RUNTIME_STAGE_ORDER: tuple[RuntimeStage, ...] = tuple(RuntimeStage)


@dataclass(frozen=True, slots=True)
class CapabilitySpec:
    id: str
    version: str
    display_name: str
    description: str
    provider_id: str
    scopes: frozenset[str]
    input_schema: Mapping[str, Any]
    output_schema: Mapping[str, Any]
    permissions: tuple[str, ...] = ()
    risk: CapabilityRisk = CapabilityRisk.READ_ONLY
    approval_required: bool = False
    resource_scope: str = "scope"
    reversible: bool = False
    aliases: tuple[str, ...] = ()
    emits: tuple[str, ...] = ()
    tags: frozenset[str] = frozenset()

    def public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "version": self.version,
            "display_name": self.display_name,
            "description": self.description,
            "provider_id": self.provider_id,
            "scopes": sorted(self.scopes),
            "input_schema": dict(self.input_schema),
            "output_schema": dict(self.output_schema),
            "permissions": list(self.permissions),
            "risk": self.risk.value,
            "approval_required": self.approval_required,
            "resource_scope": self.resource_scope,
            "reversible": self.reversible,
            "aliases": list(self.aliases),
            "emits": list(self.emits),
            "tags": sorted(self.tags),
        }


@dataclass(frozen=True, slots=True)
class RuntimeRequest:
    goal: str = ""
    capability_id: str | None = None
    arguments: Mapping[str, Any] = field(default_factory=dict)
    conversation_id: str | None = None
    request_id: str | None = None
    approval_id: str | None = None


@dataclass(frozen=True, slots=True)
class RuntimePlan:
    capability_id: str
    arguments: Mapping[str, Any]
    reason: str


@dataclass(frozen=True, slots=True)
class CapabilityExecutionResult:
    value: Mapping[str, Any]
    resource_type: str | None = None
    resource_id: str | None = None
    event_payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RuntimeResponse:
    run_id: str
    status: str
    capability_id: str | None
    decision: AuthorizationDecision
    result: Mapping[str, Any] | None
    done: bool
    trace: tuple[Mapping[str, Any], ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "capability_id": self.capability_id,
            "decision": self.decision.value,
            "result": dict(self.result) if self.result is not None else None,
            "done": self.done,
            "trace": [dict(step) for step in self.trace],
        }