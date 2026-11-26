"""Task-scoped native computer tools using the migrated isolated runner.

This module is deliberately not exposed on public chat until the trusted
capability policy and sandbox spend reservation are wired at the call site.
No host shell, provider tokens, raw runtime IDs or network access are exposed.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
from pathlib import PurePosixPath
from time import monotonic
from typing import Any

from .computer import ComputerScope, ScopedComputerTransport


@dataclass(frozen=True)
class ComputerRunGrant:
    """An already-authorized, already-budgeted run from trusted service code."""
    scope: ComputerScope
    max_calls: int = 12
    deadline_seconds: int = 180

    def __post_init__(self):
        if (not isinstance(self.scope, ComputerScope)
                or type(self.max_calls) is not int or not 1 <= self.max_calls <= 24
                or type(self.deadline_seconds) is not int or not 60 <= self.deadline_seconds <= 600):
            raise ValueError("Invalid computer run grant")


def _path(value: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 1024 or "\x00" in value:
        raise ValueError("Invalid workspace path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("Workspace-relative paths only")
    return str(path)


class ComputerRun:
    """Lazy allocation, serialized native operations and explicit cleanup.

    An ambiguous allocation or operation is never automatically replayed.
    A failed allocation can leave an orphan until provider TTL; no cleanup
    claim is made without a signed destroy receipt.
    """
    def __init__(self, transport: ScopedComputerTransport, grant: ComputerRunGrant):
        self._transport = transport
        self._grant = grant
        self._deadline = monotonic() + grant.deadline_seconds
        self._remaining = grant.max_calls
        self._lock = asyncio.Lock()
        self._sandbox_id: str | None = None
        self._allocation_attempted = False
        self._blocked = False
        self._closed = False
        self.cleanup_confirmed: bool | None = None

    def _time_left(self):
        remaining = self._deadline - monotonic()
        if remaining <= 0:
            raise TimeoutError("Computer run deadline reached")
        return remaining

    async def execute(self, tool_id: str, args: dict) -> dict:
        async with self._lock:
            if self._closed or self._blocked or self._remaining <= 0:
                raise RuntimeError("Computer run stopped or budget exhausted")
            self._time_left()
            self._remaining -= 1
            try:
                if self._sandbox_id is None:
                    self._allocation_attempted = True
                    allocated = await asyncio.wait_for(
                        self._transport.create(scope=self._grant.scope, profile="coding",
                            ttl_seconds=max(60, min(1800, self._grant.deadline_seconds + 120))),
                        timeout=self._time_left())
                    self._sandbox_id = allocated["id"]
                return await asyncio.wait_for(self._transport.execute_authorized(
                    sandbox_id=self._sandbox_id, scope=self._grant.scope,
                    tool_id=tool_id, args=args), timeout=self._time_left())
            except BaseException:
                # Cancellation, network failures and unknown provider outcomes
                # do not authorize another operation or a second allocation.
                self._blocked = True
                raise

    async def close(self) -> bool:
        async with self._lock:
            if self._closed:
                return self.cleanup_confirmed is True
            self._closed = True
            if self._sandbox_id is None:
                self.cleanup_confirmed = not self._allocation_attempted
                return self.cleanup_confirmed
            try:
                result = await asyncio.wait_for(self._transport.destroy_authorized(
                    self._sandbox_id, scope=self._grant.scope), timeout=30)
                self.cleanup_confirmed = result.get("destroyed") is True
            except Exception:
                self.cleanup_confirmed = False
            return self.cleanup_confirmed is True


def computer_tools(run: ComputerRun) -> list:
    """Native LangChain tools; scope and VM identifiers are captured server-side."""
    from langchain_core.tools import tool, ToolException

    async def execute(tool_id: str, args: dict):
        try:
            output = await run.execute(tool_id, args)
        except Exception:
            raise ToolException("Computer operation unavailable or unconfirmed; do not replay blindly") from None
        # Preserve useful stdout/stderr for repair while bounding model context.
        if not isinstance(output, dict):
            raise ToolException("Invalid computer response") from None
        safe = {k: v for k, v in output.items() if k not in {"id", "session_id", "sandbox_id"}}
        packed = json.dumps(safe, default=str, ensure_ascii=False)
        if len(packed) > 32000:
            safe = {"preview": packed[:30000], "truncated": True,
                    "ok": output.get("ok") is True}
        if (output.get("ok") is not True or output.get("timed_out") is True
                or ("exit_code" in output and output["exit_code"] != 0)):
            raise ToolException(json.dumps(safe, default=str)) from None
        return safe

    @tool
    async def computer_shell(command: str, cwd: str = ".", timeout_seconds: int = 30) -> dict:
        """Run a bounded shell command in the isolated task VM, not the API host. Network is off."""
        if not isinstance(command, str) or not 1 <= len(command) <= 16000:
            raise ToolException("Invalid bounded shell command")
        if not 1 <= timeout_seconds <= 60:
            raise ToolException("Invalid command deadline")
        return await execute("terminal.exec", {"command":command, "cwd":_path(cwd),
                                                "timeout_seconds":timeout_seconds})

    @tool
    async def computer_python(code: str, cwd: str = ".", timeout_seconds: int = 30) -> dict:
        """Execute Python in the isolated task VM; suitable for deterministic computation and tests."""
        if not isinstance(code, str) or not 1 <= len(code) <= 32000 or not 1 <= timeout_seconds <= 60:
            raise ToolException("Invalid bounded Python request")
        return await execute("python.exec", {"code":code, "cwd":_path(cwd),
                                              "timeout_seconds":timeout_seconds})

    @tool
    async def computer_read_file(path: str) -> dict:
        """Read a workspace-relative file in the task VM; output is bounded."""
        return await execute("files.read", {"path":_path(path), "max_bytes":24000})

    @tool
    async def computer_write_file(path: str, content: str) -> dict:
        """Write text into the task VM workspace. This does not publish a user artifact."""
        if not isinstance(content, str) or len(content.encode()) > 200000:
            raise ToolException("Computer text file exceeds bound")
        return await execute("files.write", {"path":_path(path), "content":content})

    @tool
    async def computer_list_files(path: str = ".") -> dict:
        """List files in a workspace-relative directory of the task VM."""
        return await execute("files.list", {"path":_path(path), "max_entries":200})

    @tool
    async def computer_search_files(query: str, path: str = ".") -> dict:
        """Search text inside the task VM workspace, with bounded results."""
        if not isinstance(query, str) or not 1 <= len(query) <= 500:
            raise ToolException("Invalid file search query")
        return await execute("files.search", {"path":_path(path), "query":query,
                                               "max_matches":100})

    bound = [computer_shell, computer_python, computer_read_file, computer_write_file,
             computer_list_files, computer_search_files]
    for item in bound:
        item.handle_tool_error = True
        item.handle_validation_error = "Invalid computer arguments; inspect the tool schema."
    return bound
