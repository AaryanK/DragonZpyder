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

from deepagents import create_deep_agent
from deepagents.backends import StateBackend
from deepagents.middleware import FilesystemMiddleware
from langchain_openrouter import ChatOpenRouter
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

_ID = re.compile(r"^[a-zA-Z0-9_.-]{1,80}$")


def configured_model() -> str:
    model = os.getenv("DRAGONZPYDER_AGENT_MODEL_ID", "").strip()
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
    """Use existing Langfuse project; never log unconfigured secret values."""
    if not all(os.getenv(k) for k in (
        "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_BASE_URL"
    )):
        return []
    from langfuse.langchain import CallbackHandler
    return [CallbackHandler()]


class AgentRuntime:
    def __init__(self) -> None:
        self._stack = AsyncExitStack()
        self._checkpointer = None

    async def start(self) -> None:
        if os.getenv("DRAGONZPYDER_AGENTS_ENABLED") != "1":
            raise RuntimeError("Agent runtime feature flag is disabled")
        if not os.getenv("OPENROUTER_API_KEY"):
            raise RuntimeError("OpenRouter credential is missing")
        configured_model()
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

    async def run(self, *, service_id: str, thread_id: str, prompt: str) -> str:
        if self._checkpointer is None:
            raise RuntimeError("Agent runtime is not started")
        if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 12000:
            raise ValueError("Prompt must be 1–12000 characters")
        key = thread_key(service_id, thread_id)
        model = ChatOpenRouter(
            model=configured_model(),
            api_key=os.environ["OPENROUTER_API_KEY"],
            max_tokens=768,
            max_retries=0,
        )
        # StateBackend is checkpointed virtual files, NOT the host filesystem.
        # No write, execute, browser, network, or real-world tool is exposed.
        agent = create_deep_agent(
            model=model,
            backend=StateBackend(),
            middleware=[FilesystemMiddleware(
                tools=["read_file", "ls", "glob", "grep"]
            )],
            checkpointer=self._checkpointer,
            system_prompt=(
                "You are DragonZpyder's general-purpose assistant. "
                "Do not claim to have executed actions without tool results."
            ),
        )
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": prompt}]},
            config={
                "configurable": {"thread_id": key},
                "recursion_limit": 16,
                "callbacks": telemetry_callbacks(),
                "metadata": {"service_id": service_id},
            },
        )
        messages = result.get("messages", [])
        if not messages:
            raise RuntimeError("Agent produced no messages")
        last = messages[-1]
        content = getattr(last, "content", "")
        if isinstance(content, str):
            return content
        return str(content)
