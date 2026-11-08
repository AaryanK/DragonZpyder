"""Bounded Deep Agents runtime with LangGraph PostgreSQL checkpoints.

This internal runtime intentionally exposes no real-world tools. A signed,
scope-limited capability delegation API is required before enabling computer
execution or workspace operations from agent prompts.
"""
from __future__ import annotations

import hashlib
import os
import re
from contextlib import AsyncExitStack
from typing import Any
from urllib.parse import urlsplit

# Restrict checkpoint deserialization to built-in types before importing LangGraph.
os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")

from deepagents import create_deep_agent
from deepagents.backends import StateBackend
from deepagents.middleware import FilesystemMiddleware
from langchain_openrouter import ChatOpenRouter
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

_ID = re.compile(r"^[a-zA-Z0-9_.-]{1,80}$")


def configured_model(model_override: str | None = None) -> str:
    model = (model_override if model_override is not None else
             os.getenv("DRAGONZPYDER_AGENT_MODEL_ID", "")).strip()
    allowed = {
        item.strip()
        for item in os.getenv(
            "DRAGONZPYDER_RUNTIME_ALLOWED_MODELS", "openai/gpt-oss-120b"
        ).split(",")
        if item.strip()
    }
    if not model or model not in allowed:
        raise RuntimeError("Agent model must be in the DragonZpyder allowlist")
    return model


def thread_key(service_id: str, thread_id: str) -> str:
    """Isolate checkpoint threads by trusted service identity, not user input."""
    if not _ID.fullmatch(service_id) or not _ID.fullmatch(thread_id):
        raise ValueError("Invalid service or thread identifier")
    return hashlib.sha256(
        (service_id + "\x00" + thread_id).encode("utf-8")
    ).hexdigest()


def telemetry_callbacks(service_id: str = "") -> list:
    """Only trace *synthetic staging evaluations* with explicit Langfuse opt-in.

    The LangChain handler includes prompts/outputs. Do not enable it on
    passworded, user-supplied /test prompts or personal chat by accident.
    No credentials are logged and no trace-delivery claim is made here.
    """
    if (os.getenv("DRAGONZPYDER_STAGING_LANGFUSE_ENABLED") != "1"
            or service_id not in ("frontier-stress", "paid-tool-smoke")):
        return []
    aliases = {
        "LANGFUSE_PUBLIC_KEY": "DRAGONZPYDER_LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY": "DRAGONZPYDER_LANGFUSE_SECRET_KEY",
        "LANGFUSE_BASE_URL": "DRAGONZPYDER_LANGFUSE_HOST",
    }
    for target, existing in aliases.items():
        if not os.getenv(target) and os.getenv(existing):
            os.environ[target] = os.environ[existing]
    if not all(os.getenv(k) for k in aliases):
        return []
    from langfuse import get_client
    from langfuse.langchain import CallbackHandler
    get_client()
    return [CallbackHandler()]


class AgentPipelineError(RuntimeError):
    """Internal phase label; original exception is retained as __cause__."""

    def __init__(self, phase: str):
        super().__init__("Agent pipeline failed")
        self.phase = phase


def build_agent(model, checkpointer):
    """Construct the enabled agent harness without executing a model call."""
    if os.getenv("DRAGONZPYDER_AGENT_HARNESS_V2") == "1":
        from .harness import build_frontier_agent
        models = {}
        for role in ("analyst", "verifier", "researcher", "builder"):
            configured = os.getenv("DRAGONZPYDER_AGENT_" + role.upper() + "_MODEL_ID", "").strip()
            if configured:
                models[role] = model_client(model_override=configured)
        return build_frontier_agent(model, checkpointer, specialist_models=models)
    backend = StateBackend()
    # A replacement filesystem middleware must explicitly use the same backend.
    return create_deep_agent(
        model=model,
        backend=backend,
        middleware=[FilesystemMiddleware(
            backend=backend,
            tools=["read_file", "ls", "glob", "grep"],
        )],
        checkpointer=checkpointer,
        system_prompt=(
            "You are DragonZpyder's general-purpose assistant. "
            "Do not claim to have executed actions without tool results."
        ),
    )


def model_client(*, model_override: str | None = None):
    """Agent inference is metered by DragonZpyder when gateway mode is enabled."""
    model = configured_model(model_override)
    # Reasoning-capable providers may use the first hundreds of output tokens
    # before producing visible tool calls. Only a paid, operator-approved
    # stress test increases this *per call* ceiling; it does not relax model
    # allowlists, gateway price caps or supervisor/delegation limits.
    stress_mode = (
        os.getenv("DRAGONZPYDER_AGENT_STRESS_EVAL_ENABLED") == "1"
        and os.getenv("DRAGONZPYDER_AGENT_EVAL_ALLOW_PAID") == "1"
    )
    output_tokens = 2048 if stress_mode else 768
    retry_count = 1 if stress_mode else 0  # Only inference; no tool action yet.
    gateway = os.getenv("DRAGONZPYDER_AGENT_USE_GATEWAY") == "1"
    if gateway:
        base = os.getenv("DRAGONZPYDER_AGENT_GATEWAY_BASE_URL", "").rstrip("/")
        parsed = urlsplit(base)
        token = os.getenv("DRAGONZPYDER_AGENT_GATEWAY_TOKEN", "")
        valid_origin = (parsed.scheme == "https" or
                        (parsed.scheme == "http" and
                         parsed.hostname and parsed.hostname.endswith(".railway.internal")))
        if (not valid_origin or not parsed.hostname or parsed.username or parsed.password or
                parsed.query or parsed.fragment or not parsed.path.endswith("/internal/agent/v1") or
                len(token) < 32):
            raise RuntimeError("A private, authenticated DragonZpyder agent gateway is required")
        return ChatOpenAI(
            base_url=base,
            api_key=token,
            model=model,
            max_tokens=output_tokens,
            max_retries=retry_count,
            timeout=60,
        )
    if os.getenv("DRAGONZPYDER_AGENT_PRODUCTION_MODE") == "1":
        raise RuntimeError("Direct OpenRouter inference is forbidden in production mode")
    key = os.getenv("OPENROUTER_API_KEY", "")
    if not key:
        raise RuntimeError("OpenRouter credential is missing")
    return ChatOpenRouter(
        model=model,
        api_key=key,
        max_tokens=output_tokens,
        max_retries=retry_count,
    )


def summarize_checkpoint_evidence(values: Any, *, termination_reason: str) -> dict:
    """Recover observable tool receipts from LangGraph's last checkpoint.

    This is an INCOMPLETE result, never a successful task or content oracle.
    No prompt, model text, tool arguments, or raw tool results leave this API.
    """
    from .artifact_evidence import artifact_readback_paths
    state = values if isinstance(values, dict) else {}
    messages = state.get("messages", [])
    if not isinstance(messages, list):
        messages = []
    files = state.get("files", {})
    files = files if isinstance(files, dict) else {}
    successful: list[str] = []
    failed = 0
    for msg in messages:
        if getattr(msg, "type", None) != "tool":
            continue
        if getattr(msg, "status", "success") == "error":
            failed += 1
        else:
            name = getattr(msg, "name", "")
            if isinstance(name, str) and name:
                successful.append(name)
    try:
        readbacks = artifact_readback_paths(messages, files)
    except (ValueError, TypeError, KeyError):
        readbacks = []
    return {
        "answer": "Agent stopped before completing the task; checkpoint evidence is partial.",
        "status": "incomplete",
        "termination_reason": termination_reason,
        "successful_tools": successful[:80],
        "failed_tool_count": failed,
        "virtual_artifact_paths": list(files.keys())[:30],
        "artifact_readback_paths": readbacks,
        "objective_verified": False,
        "checkpoint_recovered": bool(state),
    }


def controlled_termination_reason(exc: Exception) -> str | None:
    """Only recognized bounded agent loops qualify for partial recovery."""
    name = type(exc).__name__
    return {
        "GraphRecursionError": "graph_recursion_limit",
        "ModelCallLimitExceededError": "model_call_limit",
        "ToolCallLimitExceededError": "tool_call_limit",
    }.get(name)


def summarize_agent_result(result: dict) -> dict:
    """Extract UI/evaluator-safe evidence without exposing model tool arguments."""
    messages = result.get("messages", []) if isinstance(result, dict) else []
    if not messages:
        raise RuntimeError("Agent produced no messages")
    last = messages[-1]
    if getattr(last, "type", None) != "ai":
        raise RuntimeError("Agent run did not produce a final assistant message")
    content = getattr(last, "content", "")
    if not isinstance(content, str):
        content = str(content)
    if not content.strip():
        raise RuntimeError("Agent returned an empty final answer")
    from .progress_guard import STOP_PREFIX
    incomplete = content.startswith(STOP_PREFIX)
    successful = []
    failures = 0
    for message in messages:
        if getattr(message, "type", None) != "tool":
            continue
        if getattr(message, "status", "success") == "error":
            failures += 1
            continue
        name = getattr(message, "name", "")
        if isinstance(name, str) and name:
            successful.append(name)
    files = result.get("files", {})
    artifacts = list(files.keys())[:30] if isinstance(files, dict) else []
    from .artifact_evidence import artifact_readback_paths
    readback_paths = artifact_readback_paths(messages, files)
    raw_todos = result.get("todos", [])
    todos = raw_todos[:30] if isinstance(raw_todos, list) else []
    return {
        "answer": content,
        "status": "incomplete" if incomplete else "completed",
        "termination_reason": (
            content[len(STOP_PREFIX):].split(";", 1)[0].strip()
            if incomplete else None
        ),
        "successful_tools": successful[:80],
        "failed_tool_count": failures,
        "virtual_artifact_paths": artifacts,
        "artifact_readback_paths": readback_paths,
        "todos": todos,
        # External effects and objective correctness require separate checks.
        "objective_verified": False,
    }



class AgentRuntime:
    def __init__(self) -> None:
        self._stack = AsyncExitStack()
        self._checkpointer = None

    async def start(self) -> None:
        if os.getenv("DRAGONZPYDER_AGENTS_ENABLED") != "1":
            raise RuntimeError("Agent runtime feature flag is disabled")
        model_client()  # Validate the model and gateway credentials at startup.
        if os.getenv("DRAGONZPYDER_AGENT_REQUIRE_MODEL_PREFLIGHT") == "1":
            # Operator-enabled fail-closed catalog preflight BEFORE opening a
            # checkpoint or paying for inference. This only checks advertised
            # capabilities; an actual model tool loop must still be smoke-tested.
            from .model_capabilities import preflight_tool_model
            selected = {configured_model()}
            for role in ("analyst", "verifier", "researcher", "builder"):
                override = os.getenv(
                    "DRAGONZPYDER_AGENT_" + role.upper() + "_MODEL_ID", ""
                ).strip()
                if override:
                    selected.add(configured_model(override))
            for candidate in sorted(selected):
                await preflight_tool_model(candidate)
        dsn = os.getenv("DRAGONZPYDER_AGENT_DATABASE_URL", "")
        if not dsn.startswith(("postgres://", "postgresql://")):
            raise RuntimeError("A dedicated PostgreSQL checkpoint DSN is required")
        self._checkpointer = await self._stack.enter_async_context(
            AsyncPostgresSaver.from_conn_string(dsn)
        )
        await self._checkpointer.setup()

    async def close(self) -> None:
        await self._stack.aclose()
        self._checkpointer = None

    async def run_report(self, *, service_id: str, thread_id: str, prompt: str,
                         recover_partial_on_failure: bool = False) -> dict:
        if self._checkpointer is None:
            raise RuntimeError("Agent runtime is not started")
        if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 12000:
            raise ValueError("Prompt must be 1–12000 characters")
        key = thread_key(service_id, thread_id)
        model = model_client()
        from .delegation_trace import DelegationTrace
        delegation_trace = DelegationTrace()
        try:
            agent = build_agent(model, self._checkpointer)
        except Exception as exc:
            raise AgentPipelineError("construction") from exc
        config = {
            "configurable": {"thread_id": key},
            "recursion_limit": (
                96 if all(os.getenv(flag) == "1" for flag in (
                    "DRAGONZPYDER_AGENT_HARNESS_V2",
                    "DRAGONZPYDER_AGENT_STRESS_EVAL_ENABLED",
                    "DRAGONZPYDER_AGENT_EVAL_ALLOW_PAID",
                    "DRAGONZPYDER_AGENT_USE_GATEWAY",
                    "DRAGONZPYDER_AGENT_PRODUCTION_MODE",
                )) else
                32 if os.getenv("DRAGONZPYDER_AGENT_HARNESS_V2") == "1" else 16
            ),
            "callbacks": [delegation_trace, *telemetry_callbacks(service_id)],
            "metadata": {
                "service_id": service_id,
                "harness_version": "v2" if os.getenv(
                    "DRAGONZPYDER_AGENT_HARNESS_V2") == "1" else "v1",
                "langfuse_tags": ["dragonzpyder", "staging", service_id],
                "langfuse_session_id": key,
            },
        }
        try:
            result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": prompt}]},
                config=config,
            )
        except Exception as exc:
            reason = controlled_termination_reason(exc)
            if not recover_partial_on_failure or not reason:
                raise AgentPipelineError("execution") from exc
            # Persisted checkpoints can survive a model-call / recursion
            # limit. A read failure degrades evidence; it does NOT certify
            # failure as success or trigger another paid model request.
            try:
                snapshot = await agent.aget_state(config)
                state = getattr(snapshot, "values", None)
            except Exception:
                state = None
            report = summarize_checkpoint_evidence(
                state, termination_reason=reason
            )
        else:
            report = summarize_agent_result(result)
        trace = delegation_trace.snapshot()
        report["execution_id"] = trace["execution_id"]
        report["delegation_spans"] = trace["spans"]
        report["parallelism_observed"] = trace["parallelism_observed"]
        report["delegated_calls_observed"] = trace["delegated_calls_observed"]
        report["unfinished_delegation_calls"] = trace["unfinished_calls"]
        return report

    async def run_parallel_report(
        self, *, service_id: str, thread_id: str, tracks: list[dict],
    ) -> dict:
        """Reject paid fan-out until the gateway atomically enforces parent spend.

        Offline LangGraph fan-out remains testable in orchestration.py. Merely
        setting environment flags must never authorize unbounded paid children.
        """
        if self._checkpointer is None:
            raise RuntimeError("Parent agent runtime is not started")
        required = (
            "DRAGONZPYDER_AGENT_PARALLEL_EVAL_ENABLED",
            "DRAGONZPYDER_AGENT_STRESS_EVAL_ENABLED",
            "DRAGONZPYDER_AGENT_EVAL_ALLOW_PAID",
            "DRAGONZPYDER_AGENT_USE_GATEWAY",
            "DRAGONZPYDER_AGENT_PRODUCTION_MODE",
            "DRAGONZPYDER_AGENT_HARNESS_V2",
        )
        if any(os.getenv(flag) != "1" for flag in required):
            raise RuntimeError("Paid parallel evaluation is disabled")
        if not _ID.fullmatch(service_id) or not _ID.fullmatch(thread_id):
            raise ValueError("Invalid parent identity or thread")
        from .orchestration import validate_tracks
        validate_tracks(tracks)
        # SECURITY: The gateway currently enforces per-request limits, but
        # cannot reserve one shared USD ceiling atomically across child runs.
        # Multiple independent metered calls may exhaust a parent budget even
        # with all opt-in flags set. Do not enable paid fan-out on flags alone.
        # Remove this guard ONLY in the same reviewed change that binds every
        # child inference request to an authenticated, gateway-enforced atomic
        # parent reservation (including retry/timeout and unknown-cost cases).
        raise RuntimeError(
            "Paid parallel evaluation disabled: atomic shared gateway budget "
            "enforcement is not implemented"
        )

    async def run(self, *, service_id: str, thread_id: str, prompt: str) -> str:
        """Backward-compatible Hatchet/API adapter: plain answer only."""
        report = await self.run_report(
            service_id=service_id, thread_id=thread_id, prompt=prompt
        )
        return report["answer"]
