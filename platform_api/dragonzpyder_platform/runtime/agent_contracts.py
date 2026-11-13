from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from hashlib import sha256
from typing import Any, Mapping


class AgentRunStatus(StrEnum):
    COMPLETED = "completed"
    WAITING_APPROVAL = "waiting_approval"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BUDGET_EXHAUSTED = "budget_exhausted"
    EXECUTION_UNCERTAIN = "execution_uncertain"


class AgentStepStatus(StrEnum):
    COMPLETED = "completed"
    WAITING_APPROVAL = "waiting_approval"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXECUTION_UNCERTAIN = "execution_uncertain"


@dataclass(frozen=True, slots=True)
class AgentBudget:
    max_steps: int = 24
    max_mutations: int = 8

    def __post_init__(self) -> None:
        if not 1 <= self.max_steps <= 128:
            raise ValueError("max_steps must be between 1 and 128")
        if not 0 <= self.max_mutations <= 64:
            raise ValueError("max_mutations must be between 0 and 64")


@dataclass(frozen=True, slots=True)
class AgentPlanStep:
    step_id: str
    capability_id: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    approval_id: str | None = None

    def __post_init__(self) -> None:
        step_id = str(self.step_id or "").strip()
        capability_id = str(self.capability_id or "").strip()
        if not step_id or len(step_id) > 120:
            raise ValueError("step_id must contain 1-120 characters")
        if not capability_id or len(capability_id) > 200:
            raise ValueError("capability_id must contain 1-200 characters")
        object.__setattr__(self, "step_id", step_id)
        object.__setattr__(self, "capability_id", capability_id)
        object.__setattr__(self, "arguments", dict(self.arguments))
        approval_id = str(self.approval_id or "").strip() or None
        if approval_id is not None and len(approval_id) > 36:
            raise ValueError("approval_id must be at most 36 characters")
        object.__setattr__(self, "approval_id", approval_id)


@dataclass(frozen=True, slots=True)
class AgentPlan:
    run_id: str
    goal: str
    steps: tuple[AgentPlanStep, ...]
    budget: AgentBudget = field(default_factory=AgentBudget)

    def __post_init__(self) -> None:
        run_id = str(self.run_id or "").strip()
        goal = str(self.goal or "").strip()
        if not run_id or len(run_id) > 120:
            raise ValueError("run_id must contain 1-120 characters")
        if not goal or len(goal) > 12_000:
            raise ValueError("goal must contain 1-12000 characters")
        steps = tuple(self.steps)
        if not steps:
            raise ValueError("Agent plan must contain at least one step")
        step_ids = [step.step_id for step in steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("Agent plan step_id values must be unique")
        object.__setattr__(self, "run_id", run_id)
        object.__setattr__(self, "goal", goal)
        object.__setattr__(self, "steps", steps)


@dataclass(frozen=True, slots=True)
class AgentStepResult:
    step_id: str
    capability_id: str
    request_id: str
    status: AgentStepStatus
    kernel_run_id: str | None = None
    result: Mapping[str, Any] | None = None
    approval_id: str | None = None
    error_code: str | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class AgentRunResult:
    run_id: str
    status: AgentRunStatus
    steps: tuple[AgentStepResult, ...]
    next_step_id: str | None = None
    approval_id: str | None = None
    error_code: str | None = None
    error: str | None = None

    @property
    def done(self) -> bool:
        return self.status in {
            AgentRunStatus.COMPLETED,
            AgentRunStatus.FAILED,
            AgentRunStatus.CANCELLED,
            AgentRunStatus.BUDGET_EXHAUSTED,
            AgentRunStatus.EXECUTION_UNCERTAIN,
        }


def stable_step_request_id(run_id: str, step_id: str) -> str:
    """Return one bounded mutation identity for one logical agent step.

    Resuming an approval or retrying after a lost response must reuse this exact ID.
    It deliberately contains no model-supplied capability or arguments; Kernel binds
    the ID to the canonical capability and planned arguments and rejects conflicts.
    """

    identity = f"{str(run_id).strip()}\0{str(step_id).strip()}".encode("utf-8")
    return f"agent-step:{sha256(identity).hexdigest()}"