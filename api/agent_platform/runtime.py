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


def telemetry_callbacks() -> list:
    """Reuse the current gateway's Langfuse project when configured."""
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
        for role in ("analyst", "verifier", "researcher"):
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
    raw_todos = result.get("todos", [])
    todos = raw_todos[:30] if isinstance(raw_todos, list) else []
    return {
        "answer": content,
        "successful_tools": successful[:80],
        "failed_tool_count": failures,
        "virtual_artifact_paths": artifacts,
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

    async def run_report(self, *, service_id: str, thread_id: str, prompt: str) -> dict:
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
        try:
            result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": prompt}]},
                config={
                    "configurable": {"thread_id": key},
                    "recursion_limit": (
                        32 if os.getenv("DRAGONZPYDER_AGENT_HARNESS_V2") == "1" else 16
                    ),
                    "callbacks": [delegation_trace, *telemetry_callbacks()],
                    "metadata": {
                        "service_id": service_id,
                        "harness_version": (
                            "v2" if os.getenv("DRAGONZPYDER_AGENT_HARNESS_V2") == "1"
                            else "v1"
                        ),
                    },
                },
            )
        except Exception as exc:
            raise AgentPipelineError("execution") from exc
        report = summarize_agent_result(result)
        trace = delegation_trace.snapshot()
        report["delegation_spans"] = trace["spans"]
        report["parallelism_observed"] = trace["parallelism_observed"]
        report["delegated_calls_observed"] = trace["delegated_calls_observed"]
        report["unfinished_delegation_calls"] = trace["unfinished_calls"]
        return report

    async def run_parallel_report(
        self, *, service_id: str, thread_id: str, tracks: list[dict],
    ) -> dict:
        """Explicit LangGraph parallel agents; gated metered STAGING evaluation.

        Each track uses its own PostgreSQL checkpoint connection and thread.
        This is not a personal computer, an approved external write, or a
        frontier benchmark pass. Global USD caps must be configured separately.
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
        from .orchestration import run_parallel_tracks, validate_tracks
        validate_tracks(tracks)

        async def run_one(track: dict) -> dict:
            # A fresh connection per concurrently executing LangGraph task
            # avoids sharing one single-connection Postgres saver concurrently.
            child = AgentRuntime()
            await child.start()
            try:
                key = hashlib.sha256(
                    (thread_id + "\\x00" + track["id"]).encode("utf-8")
                ).hexdigest()[:32]
                return await child.run_report(
                    service_id=service_id,
                    thread_id="parallel-" + key,
                    prompt=track["prompt"],
                )
            finally:
                await child.close()

        return await run_parallel_tracks(tracks, run_one)

    async def run(self, *, service_id: str, thread_id: str, prompt: str) -> str:
        """Backward-compatible Hatchet/API adapter: plain answer only."""
        report = await self.run_report(
            service_id=service_id, thread_id=thread_id, prompt=prompt
        )
        return report["answer"]
