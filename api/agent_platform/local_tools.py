"""Read-only local computer capabilities for DragonZpyder's worker process.

These tools are operator-defined: no shell, network, arbitrary paths, process
enumeration, credentials, or prompt-supplied capability registrations.
They observe the worker environment, not the user's personal laptop.
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


class LocalToolError(ValueError):
    """Unknown capability or prohibited arguments."""


def _number(path: str) -> int | None:
    try:
        raw = Path(path).read_text(encoding="ascii").strip()
        if raw == "max":
            return None
        value = int(raw)
        return value if value >= 0 else None
    except (OSError, ValueError, UnicodeDecodeError):
        return None


def _host_memory() -> tuple[int, int]:
    try:
        values: dict[str, int] = {}
        for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            if key in {"MemTotal", "MemAvailable"}:
                values[key] = int(value.strip().split()[0]) * 1024
        if values.get("MemTotal", 0) > 0 and values.get("MemAvailable") is not None:
            return values["MemTotal"], min(values["MemTotal"], values["MemAvailable"])
    except (OSError, UnicodeDecodeError, ValueError, IndexError):
        pass
    try:
        import psutil
        info = psutil.virtual_memory()
        return int(info.total), int(info.available)
    except (ImportError, AttributeError):
        pass
    raise RuntimeError("RAM metrics are unavailable on this worker")


def _memory() -> dict[str, Any]:
    total, available = _host_memory()
    scope = "host"
    ceiling = _number("/sys/fs/cgroup/memory.max")
    current = _number("/sys/fs/cgroup/memory.current")
    if ceiling is None or current is None:
        ceiling = _number("/sys/fs/cgroup/memory/memory.limit_in_bytes")
        current = _number("/sys/fs/cgroup/memory/memory.usage_in_bytes")
    if ceiling is not None and current is not None and 0 < ceiling < total:
        total = ceiling
        available = max(0, total - current)
        scope = "container"
    used = max(0, total - available)
    return {
        "scope": scope,
        "total_bytes": total,
        "used_bytes": used,
        "available_bytes": available,
        "used_percent": round(100.0 * used / total, 2),
    }


def _disk() -> dict[str, Any]:
    info = shutil.disk_usage(Path(os.path.abspath(os.sep)))
    return {
        "scope": "worker_root",
        "total_bytes": int(info.total),
        "used_bytes": int(info.used),
        "free_bytes": int(info.free),
        "used_percent": round(100.0 * info.used / info.total, 2),
    }


def _time() -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    return {"utc": now.isoformat(timespec="seconds"), "unix_seconds": int(now.timestamp())}


@dataclass(frozen=True)
class LocalToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[[], dict[str, Any]]


class LocalToolRegistry:
    """Stable, MCP-mappable schemas for three strict read-only capabilities."""

    def __init__(self) -> None:
        schema = {"type": "object", "properties": {}, "additionalProperties": False}
        self._tools = {
            item.name: item for item in (
                LocalToolSpec("time.now", "Read the worker UTC clock", schema, _time),
                LocalToolSpec("system.memory", "Read worker RAM utilization", schema, _memory),
                LocalToolSpec("system.disk", "Read worker root disk utilization", schema, _disk),
            )
        }

    def catalog(self) -> list[dict[str, Any]]:
        return [
            {"name": item.name, "description": item.description,
             "inputSchema": item.input_schema, "risk": "read_only"}
            for item in self._tools.values()
        ]

    def invoke(self, name: str, arguments: dict | None = None) -> dict[str, Any]:
        if not isinstance(name, str) or name not in self._tools:
            raise LocalToolError("Tool is not in the local allowlist")
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, dict) or arguments:
            raise LocalToolError("Read-only monitoring tools accept no arguments")
        return self._tools[name].handler()
