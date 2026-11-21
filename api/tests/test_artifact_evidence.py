"""Artifact tool-dispatch receipts: path, reply, ordering and final state."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain_core.messages import AIMessage, ToolMessage
from agent_platform.artifact_evidence import artifact_readback_paths


def ai(name, path, tool_id):
    return AIMessage(content="", tool_calls=[{
        "name": name, "args": {"file_path": path}, "id": tool_id,
    }])


def reply(name, tool_id, *, status="success", content="ok"):
    return ToolMessage(name=name, tool_call_id=tool_id, status=status, content=content)


def test_exact_write_and_later_readback_requires_checkpointed_file():
    path = "/workspace/science/field_map.md"
    messages = [
        ai("write_file", path, "w1"), reply("write_file", "w1"),
        ai("read_file", path, "r1"), reply("read_file", "r1"),
        AIMessage(content="My answer was verified"),
    ]
    assert artifact_readback_paths(messages, {path: object()}) == [path]
    assert artifact_readback_paths(messages, {}) == []


def test_unrelated_tool_read_cannot_verify_expected_file():
    expected = "/workspace/school/lesson.md"
    unrelated = "/workspace/notes/other.md"
    messages = [
        ai("write_file", expected, "w1"), reply("write_file", "w1"),
        ai("read_file", unrelated, "r1"), reply("read_file", "r1"),
    ]
    assert artifact_readback_paths(messages, {expected: object(), unrelated: object()}) == []


def test_same_turn_concurrent_read_and_write_is_not_sequential_verification():
    path = "/workspace/field.md"
    messages = [
        AIMessage(content="", tool_calls=[
            {"name": "write_file", "args": {"file_path": path}, "id": "w1"},
            {"name": "read_file", "args": {"file_path": path}, "id": "r1"},
        ]),
        reply("write_file", "w1"),
        reply("read_file", "r1"),
    ]
    assert artifact_readback_paths(messages, {path: "content"}) == []


def test_later_edit_invalidates_previous_readback():
    path = "/workspace/report.md"
    messages = [
        ai("write_file", path, "w1"), reply("write_file", "w1"),
        ai("read_file", path, "r1"), reply("read_file", "r1"),
        ai("edit_file", path, "e1"), reply("edit_file", "e1"),
    ]
    assert artifact_readback_paths(messages, {path: "edited"}) == []
    messages.extend([ai("read_file", path, "r2"), reply("read_file", "r2")])
    assert artifact_readback_paths(messages, {path: "edited"}) == [path]


def test_failed_or_mismatched_tool_reply_is_not_credit():
    path = "/workspace/report.md"
    for read_reply in (
        reply("read_file", "r1", status="error"),
        reply("read_file", "wrong-id"),
        reply("write_file", "r1"),
        reply("read_file", "r1", content="Error: permission denied"),
    ):
        messages = [
            ai("write_file", path, "w1"), reply("write_file", "w1"),
            ai("read_file", path, "r1"), read_reply,
        ]
        assert artifact_readback_paths(messages, {path: "maybe"}) == []


def test_checkpoint_path_and_tool_path_must_be_safe_and_exact():
    for path in (
        "/workspace/../secret.txt", "/private/secret.md",
        "/workspace//report.md", "/workspace/./report.md",
        "/workspace\\report.md", "/workspace/file\x00.md",
    ):
        messages = [
            ai("write_file", path, "w1"), reply("write_file", "w1"),
            ai("read_file", path, "r1"), reply("read_file", "r1"),
        ]
        assert artifact_readback_paths(messages, {path: "unsafe"}) == []


def test_duplicate_call_id_cannot_replay_a_previous_write():
    path = "/workspace/notes.md"
    messages = [
        ai("write_file", path, "same"), reply("write_file", "same"),
        ai("read_file", path, "same"), reply("read_file", "same"),
    ]
    assert artifact_readback_paths(messages, {path: "text"}) == []
