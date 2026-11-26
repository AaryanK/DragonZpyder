"""Operator-reviewed adaptive model selection within the existing agent gateway.

This policy does not make a separate paid classification call, grant tools,
retry an invocation, or widen the gateway model/price allowlist. Model
selection is a recommendation derived from observed task requirements.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass

_COMPLEX = re.compile(r"\b(?:implement|debug|investigate|analy[sz]e|compare|research|verify|design|prove|derive|refactor|simulate|optimi[sz]e|benchmark|workflow|multiple|complex|report)\b",re.I)
_SIMPLE = re.compile(r"^(?:hi|hello|hey|thanks|thank you|good (?:morning|evening)|what is your name)[.!? ]*$",re.I)


@dataclass(frozen=True)
class Route:
    tier: str
    model: str
    reason: str


def choose_route(*, objective: str, default_model: str, cheap_model: str | None,
                 reasoning_model: str | None, approved_models: frozenset[str],
                 has_tools: bool = False, has_attachments: bool = False,
                 durable: bool = False, tool_failures: int = 0) -> Route:
    if default_model not in approved_models:
        raise ValueError("Default model is not approved")
    # Never route multimodal inputs directly to a text-only cheap model.
    # Specialist media tools separately enforce reviewed modality declarations.
    if has_attachments or durable or tool_failures >= 2 or len(objective)>1600 or _COMPLEX.search(objective):
        if reasoning_model in approved_models:
            return Route("reasoning",reasoning_model,"complex_or_recovery")
        return Route("default",default_model,"reasoning_unavailable")
    if not has_tools and not has_attachments and not durable and _SIMPLE.fullmatch(objective.strip()):
        if cheap_model in approved_models:
            return Route("fast",cheap_model,"simple_conversation")
    return Route("default",default_model,"conservative_default")


def select_model(objective: str, *, has_tools=False, has_attachments=False,
                 durable=False, tool_failures=0):
    from .runtime import configured_model
    default=configured_model()
    if (os.getenv("DRAGONZPYDER_ADAPTIVE_ROUTING_ENABLED")!="1"
            or os.getenv("DRAGONZPYDER_AGENT_USE_GATEWAY")!="1"):
        return Route("default",default,"routing_disabled")
    approved=frozenset(x.strip() for x in os.getenv(
        "DRAGONZPYDER_RUNTIME_ALLOWED_MODELS","openai/gpt-oss-120b").split(",") if x.strip())
    return choose_route(objective=objective,default_model=default,
        cheap_model=os.getenv("DRAGONZPYDER_AGENT_FAST_MODEL_ID"),
        reasoning_model=os.getenv("DRAGONZPYDER_AGENT_REASONING_MODEL_ID"),
        approved_models=approved,has_tools=has_tools,has_attachments=has_attachments,
        durable=durable,tool_failures=tool_failures)


def recovery_middleware(*, initial_model, reasoning_model, max_escalations=1):
    """Switch the next model call on observed repeated failure, never replay a tool.

    This is optional per-graph middleware. It uses the same model client,
    checkpoint, middleware limits and gateway identity as the base harness.
    No model-provided flags or content can authorize an escalation.
    """
    from langchain.agents.middleware import wrap_model_call
    from .progress_guard import current_turn_messages
    from .tool_outcomes import tool_outcome

    escalated=False
    @wrap_model_call
    async def adaptive_recovery(request, handler):
        nonlocal escalated
        messages=current_turn_messages(request.state.get("messages",[]))
        failures=sum(tool_outcome(m)=="failed" for m in messages if getattr(m,"type",None)=="tool")
        # Middleware is created once per graph/request, never shared across
        # users. The escalation is sticky even if upstream compacts messages.
        if failures>=2 and max_escalations==1 and reasoning_model is not initial_model:
            escalated=True
        if escalated:
            return await handler(request.override(model=reasoning_model))
        return await handler(request)
    return adaptive_recovery


def routed_model(objective,*,model_factory,has_tools=False,has_attachments=False,
                 durable=False,parent_job_id=None):
    """Use identical selection and fallback policy across every core entrypoint."""
    kwargs={"parent_job_id":parent_job_id} if parent_job_id is not None else {}
    if os.getenv("DRAGONZPYDER_ADAPTIVE_ROUTING_ENABLED")!="1":
        return model_factory(**kwargs),None,None
    route=select_model(objective,has_tools=has_tools,has_attachments=has_attachments,durable=durable)
    model=model_factory(model_override=route.model,**kwargs)
    middleware=None
    reasoning=os.getenv("DRAGONZPYDER_AGENT_REASONING_MODEL_ID","").strip()
    if reasoning and reasoning!=route.model and os.getenv("DRAGONZPYDER_AGENT_USE_GATEWAY")=="1":
        from .runtime import configured_model
        try:configured_model(reasoning)
        except RuntimeError:pass
        else:middleware=recovery_middleware(initial_model=model,
            reasoning_model=model_factory(model_override=reasoning,**kwargs))
    return model,route,middleware
