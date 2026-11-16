"""Bounded, path-specific evidence of virtual artifact writes and readbacks.

A filename in checkpoint state plus unrelated tool traffic is not evidence of
having verified that artifact. Inspect LangChain AI tool-call IDs and their
matching successful ToolMessages in order, then require a later read of the
latest written version at exactly the same workspace path.

This is tool-dispatch evidence, NOT proof that content is correct, external
files exist, or the messages originate from an authenticated environment.
"""
from __future__ import annotations


def _workspace_path(value: object) -> str | None:
    if not isinstance(value, str) or len(value) > 500 or not value.startswith("/workspace/"):
        return None
    if "\\" in value or any(ord(c) < 32 or ord(c) == 127 for c in value):
        return None
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts[2:]):
        return None
    return value


def artifact_readback_paths(messages: object, checkpoint_files: object) -> list[str]:
    """Return exact paths observed written then read via successful tool replies.

    The read must be requested in a later assistant step, after the latest
    successful write/edit, so concurrent write+read calls are not credited.
    A later successful rewrite invalidates an earlier readback.
    """
    if not isinstance(messages, list) or not isinstance(checkpoint_files, dict):
        return []
    checkpoint_paths = {_workspace_path(path) for path in checkpoint_files}
    pending: dict[str, tuple[str, str, int]] = {}
    seen_ids: set[str] = set()
    last_write_response: dict[str, int] = {}
    observed: set[str] = set()

    # Never scan an unbounded checkpoint transcript for a single report.
    for index, message in enumerate(messages[-1000:]):
        role = getattr(message, "type", None)
        if role == "ai":
            calls = getattr(message, "tool_calls", None)
            if not isinstance(calls, list):
                continue
            for call in calls[:20]:
                if not isinstance(call, dict):
                    continue
                call_id, name, args = call.get("id"), call.get("name"), call.get("args")
                if (not isinstance(call_id, str) or not call_id or call_id in seen_ids
                    or name not in {"write_file", "edit_file", "read_file"}
                    or not isinstance(args, dict)):
                    continue
                path = _workspace_path(args.get("file_path"))
                if path is None:
                    continue
                seen_ids.add(call_id)
                pending[call_id] = (name, path, index)
        elif role == "tool":
            call_id = getattr(message, "tool_call_id", None)
            operation = pending.pop(call_id, None)
            if operation is None:
                continue
            name, path, requested_index = operation
            if (getattr(message, "status", None) != "success"
                    or getattr(message, "name", None) != name):
                continue
            content = getattr(message, "content", None)
            # Some middleware exposes denied file operations as a tool
            # response without status=error. Fail closed on known errors.
            if isinstance(content, str) and content.lstrip().lower().startswith((
                "error:", "permission denied", "file not found",
            )):
                continue
            if name in {"write_file", "edit_file"}:
                last_write_response[path] = index
                observed.discard(path)
            elif path in last_write_response and last_write_response[path] < requested_index:
                observed.add(path)

    return sorted(path for path in observed if path in checkpoint_paths)[:30]
