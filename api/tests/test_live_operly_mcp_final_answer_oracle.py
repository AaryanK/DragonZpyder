"""Regression tests for final-answer truthfulness in the isolated Operly MCP smoke."""
import json

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from agent_platform.live_operly_mcp_smoke import (
    EXPECTED_WORKSPACE,
    _final_answer_matches_receipts,
    _readback_verified,
    _tool_calls_match_receipts,
)


def _messages(answer):
    workspace = ToolMessage(
        content=json.dumps({"name": EXPECTED_WORKSPACE}),
        name="operly_workspace_describe",
        tool_call_id="workspace-1",
    )
    modules = ToolMessage(
        content=json.dumps({"modules": [
            {"key": "crm", "name": "CRM"},
            {"key": "billing", "name": "Billing"},
        ]}),
        name="operly_workspace_modules_list",
        tool_call_id="modules-1",
    )
    return [workspace, modules, AIMessage(content=answer)]


@pytest.mark.parametrize(("answer", "expected"), [
    ({"workspace": EXPECTED_WORKSPACE, "modules": ["crm", "billing"]}, True),
    ({"workspace": EXPECTED_WORKSPACE, "modules": ["billing", "crm"]}, True),
    ({"workspace": "Fake Workspace", "modules": ["crm", "billing"]}, False),
    ({"workspace": EXPECTED_WORKSPACE, "modules": ["crm"]}, False),
    ({"workspace": EXPECTED_WORKSPACE, "modules": ["crm", "billing", "invented"]}, False),
    ({"workspace": EXPECTED_WORKSPACE, "modules": ["crm", "crm"]}, False),
    ({"workspace": EXPECTED_WORKSPACE, "modules": ["crm", "billing"], "verified": True}, False),
    (["crm", "billing"], False),
])
def test_final_answer_oracle(answer, expected):
    messages = _messages(json.dumps(answer))
    tool_verified, _ = _readback_verified(messages)
    assert tool_verified
    assert _final_answer_matches_receipts(messages) is expected


def test_non_json_final_answer_fails():
    assert not _final_answer_matches_receipts(_messages("The workspace is verified."))


def test_tool_only_state_fails():
    assert not _final_answer_matches_receipts(_messages("{}")[:-1])


def test_duplicate_receipt_fails():
    messages = _messages(json.dumps({
        "workspace": EXPECTED_WORKSPACE, "modules": ["crm", "billing"]
    }))
    assert not _final_answer_matches_receipts([messages[0], messages[0], messages[1], messages[2]])


def test_tool_call_receipts_are_correlated_to_model_requests():
    request = AIMessage(content="", tool_calls=[
        {"name": "operly_workspace_describe", "args": {}, "id": "workspace-1"},
        {"name": "operly_workspace_modules_list", "args": {}, "id": "modules-1"},
    ])
    receipts = _messages(json.dumps({
        "workspace": EXPECTED_WORKSPACE, "modules": ["crm", "billing"]
    }))
    assert _tool_calls_match_receipts([request, *receipts])
    assert not _tool_calls_match_receipts(receipts)  # fabricated tool evidence
    assert not _tool_calls_match_receipts([request, receipts[0], receipts[2]])  # missing response
    assert not _tool_calls_match_receipts([request, receipts[0], receipts[0], receipts[1], receipts[2]])
    assert _tool_calls_match_receipts([request, receipts[1], receipts[0], receipts[2]])  # order independent
    wrong = ToolMessage(
        content=receipts[0].content, name="operly_workspace_modules_list",
        tool_call_id="workspace-1",
    )
    assert not _tool_calls_match_receipts([request, wrong, receipts[1], receipts[2]])
    unknown = ToolMessage(
        content=receipts[0].content, name="operly_workspace_describe",
        tool_call_id="unissued",
    )
    assert not _tool_calls_match_receipts([request, unknown, receipts[1], receipts[2]])


def test_duplicate_json_keys_in_final_answer_fail_closed():
    # Standard json.loads silently keeps the last occurrence of a key.
    # Ambiguous user-facing claims must never count as verified completion.
    duplicate_top_level = (
        '{"workspace":"Fabricated","workspace":'
        + json.dumps(EXPECTED_WORKSPACE)
        + ',"modules":["crm","billing"]}'
    )
    assert not _final_answer_matches_receipts(_messages(duplicate_top_level))
    duplicate_nested = (
        '{"workspace":' + json.dumps(EXPECTED_WORKSPACE)
        + ',"modules":["crm","billing"],"metadata":{"id":1,"id":2}}'
    )
    assert not _final_answer_matches_receipts(_messages(duplicate_nested))


@pytest.mark.parametrize(("receipt_index", "ambiguous_content"), [
    (0, '{"name":"Fabricated","name":' + json.dumps(EXPECTED_WORKSPACE) + '}'),
    (1, '{"modules":[{"key":"fake","key":"crm","name":"CRM"},'
        '{"key":"billing","name":"Billing"}]}'),
    (1, '{"modules":[{"key":"crm","name":"CRM"},'
        '{"key":"billing","name":"Billing"}],'
        '"modules":[{"key":"crm","name":"CRM"},'
        '{"key":"billing","name":"Billing"}]}'),
])
def test_duplicate_keys_in_tool_receipts_fail_closed(receipt_index, ambiguous_content):
    messages = _messages(json.dumps({
        "workspace": EXPECTED_WORKSPACE, "modules": ["crm", "billing"]
    }))
    original = messages[receipt_index]
    messages[receipt_index] = ToolMessage(
        content=ambiguous_content, name=original.name,
        tool_call_id=original.tool_call_id,
    )
    assert not _readback_verified(messages)[0]
    assert not _final_answer_matches_receipts(messages)
