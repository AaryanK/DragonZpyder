"""No-paid inference contract tests for durable model-selected local telemetry."""
import asyncio
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_platform.horizon_agent import (
    TOOLS, HorizonError, accept_model_choice, guard, model_tools,
)


def model_selection(name: str, args="{}"):
    return {"choices": [{"message": {
        "role": "assistant",
        "tool_calls": [{"type": "function", "id": "call_1",
                        "function": {"name": name, "arguments": args}}],
    }}]}


def test_only_three_approved_local_capabilities_are_exposed():
    specs = model_tools(set())
    assert {x["function"]["name"] for x in specs} == set(TOOLS)
    assert all(x["function"]["parameters"]["additionalProperties"] is False for x in specs)
    assert all(x["function"]["parameters"]["properties"] == {} for x in specs)


def test_real_model_output_must_select_one_fresh_tool():
    assert accept_model_choice(model_selection("read_worker_memory"), set()) == "system.memory"
    assert accept_model_choice(model_selection("read_utc_time"),
                               {"system.memory"}) == "time.now"
    assert {x["function"]["name"] for x in model_tools({"time.now", "system.disk"})} == {
        "read_worker_memory"
    }


@pytest.mark.parametrize("payload,used", [
    (model_selection("read_worker_memory"), {"system.memory"}),
    (model_selection("workspace.finance.payment.record"), set()),
    (model_selection("read_worker_disk", '{"path":"/etc"}'), set()),
    (model_selection("read_worker_disk", "[]"), set()),
    (model_selection("read_utc_time", "{not-json"), set()),
    ({"choices": []}, set()),
    ({"choices": [{"message": {"content": "I did it."}}]}, set()),
    ({"choices": [{"message": {"tool_calls": [
        {"function": {"name": "read_utc_time", "arguments": "{}"}},
        {"function": {"name": "read_worker_disk", "arguments": "{}"}},
    ]}}]}, set()),
])
def test_unapproved_or_untrusted_model_tool_choice_is_rejected(payload, used):
    with pytest.raises(HorizonError):
        accept_model_choice(payload, used)


def test_gateway_access_requires_private_staging_and_allowlisted_model(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_STAGE", "staging")
    monkeypatch.setenv("DRAGONZPYDER_HORIZON_CANARY_ENABLED", "1")
    monkeypatch.setenv("DRAGONZPYDER_HORIZON_DATABASE_URL", "postgresql://synthetic/db")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_GATEWAY_BASE_URL",
                       "http://dragonzpyder-gateway.railway.internal:8080/internal/agent/v1")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_GATEWAY_TOKEN", "s" * 48)
    monkeypatch.setenv("DRAGONZPYDER_HORIZON_MODEL_ID", "openai/gpt-oss-120b")
    monkeypatch.setenv("DRAGONZPYDER_RUNTIME_ALLOWED_MODELS", "openai/gpt-oss-120b")
    assert guard()[2] == "openai/gpt-oss-120b"
    monkeypatch.setenv("DRAGONZPYDER_STAGE", "production")
    with pytest.raises(HorizonError):
        guard()
    monkeypatch.setenv("DRAGONZPYDER_STAGE", "staging")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_GATEWAY_BASE_URL",
                       "https://evil.example/internal/agent/v1")
    with pytest.raises(HorizonError):
        guard()
    monkeypatch.setenv("DRAGONZPYDER_AGENT_GATEWAY_BASE_URL",
                       "http://dragonzpyder-gateway.railway.internal:8080/internal/agent/v1")
    monkeypatch.setenv("DRAGONZPYDER_HORIZON_MODEL_ID", "other/expensive-model")
    with pytest.raises(HorizonError):
        guard()
