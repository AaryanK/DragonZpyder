"""Internal agent tool-call protocol, isolated from legacy text-only gateway."""
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_platform.gateway_protocol import (
    validate_agent_body, validate_agent_response, AgentProtocolError,
)

MODEL = "openai/gpt-oss-120b"
FUNCTION = {"type":"function","function":{"name":"read_file","description":"Read virtual file",
            "parameters":{"type":"object","properties":{"path":{"type":"string"}}}}}

def test_agent_accepts_bounded_tool_calls():
    req={"model":MODEL,"messages":[
        {"role":"user","content":"Read x"},
        {"role":"assistant","content":None,"tool_calls":[{"id":"call_123","type":"function",
             "function":{"name":"read_file","arguments":'{"path":"x"}'}}]},
        {"role":"tool","content":"example","tool_call_id":"call_123"},
    ],"tools":[FUNCTION],"tool_choice":"auto","max_tokens":400}
    body=validate_agent_body(req,[MODEL])
    assert body["messages"][1]["tool_calls"][0]["function"]["name"]=="read_file"
    assert body["messages"][2]["role"]=="tool"
    assert body["max_tokens"]==400

def test_agent_rejects_unknown_and_unsafe_models_and_payloads():
    with pytest.raises(AgentProtocolError):
        validate_agent_body({"model":"other","messages":[{"role":"user","content":"x"}]},[MODEL])
    with pytest.raises(AgentProtocolError):
        validate_agent_body({"model":MODEL,"messages":[{"role":"tool","content":"x"}]},[MODEL])
    with pytest.raises(AgentProtocolError):
        validate_agent_body({"model":MODEL,"messages":[{"role":"user","content":"x"}],"tools":[{"type":"shell"}]},[MODEL])
    with pytest.raises(AgentProtocolError):
        validate_agent_body({"model":MODEL,"messages":[{"role":"user","content":"x"}],"stream":True},[MODEL])

def test_agent_tool_response_keeps_function_calls():
    provider={"id":"req1","model":MODEL,"choices":[{"message":{"role":"assistant","content":None,
        "tool_calls":[{"id":"call_123","type":"function",
          "function":{"name":"read_file","arguments":'{"path":"x"}'}}]},
        "finish_reason":"tool_calls"}],"usage":{"prompt_tokens":123,"completion_tokens":22}}
    answer=validate_agent_response(provider,MODEL)
    assert answer["choices"][0]["message"]["content"] is None
    assert answer["choices"][0]["message"]["tool_calls"][0]["id"]=="call_123"
    assert answer["usage"]["prompt_tokens"]==123

def test_agent_does_not_accept_malformed_tool_outputs():
    with pytest.raises(AgentProtocolError):
        validate_agent_response({"choices":[{"message":{"role":"assistant","tool_calls":
          [{"id":"call_1","type":"function","function":{"name":"read_file",
           "arguments":"not-json"}}]}}]},MODEL)

def test_agent_flattens_text_only_content_blocks():
    body=validate_agent_body({"model":MODEL,"messages":[
        {"role":"user","content":[{"type":"text","text":"Hello"},{"type":"text","text":"again"}]}
    ]},[MODEL])
    assert body["messages"][0]["content"] == "Hello\nagain"
    with pytest.raises(AgentProtocolError):
        validate_agent_body({"model":MODEL,"messages":[
            {"role":"user","content":[{"type":"image_url","image_url":"https://example.invalid/"}]}
        ]},[MODEL])



def test_openai_compatible_empty_tool_call_list_is_normal_text():
    provider = {"choices": [{"message": {"role": "assistant",
                  "content": "Finished successfully.", "tool_calls": []},
                  "finish_reason": "stop"}]}
    res = validate_agent_response(provider, MODEL)
    assert res["choices"][0]["message"]["content"] == "Finished successfully."
    assert "tool_calls" not in res["choices"][0]["message"]


def test_reasoning_only_output_without_visible_content_is_not_success():
    provider = {"choices": [{"message": {"role": "assistant",
                  "content": None, "reasoning": "private reasoning",
                  "tool_calls": []}, "finish_reason": "length"}]}
    with pytest.raises(AgentProtocolError, match="output limit"):
        validate_agent_response(provider, MODEL)


def test_agent_tool_requests_require_compatible_provider_without_injected_temperature():
    payload = validate_agent_body({
        "model": MODEL, "messages": [{"role": "user", "content": "Read it"}],
        "tools": [FUNCTION], "max_tokens": 1024,
    }, [MODEL])
    assert payload["provider"] == {"require_parameters": True}
    assert "temperature" not in payload
    explicit = validate_agent_body({
        "model": MODEL, "messages": [{"role": "user", "content": "Hello"}],
        "temperature": 0.7,
    }, [MODEL])
    assert explicit["temperature"] == 0.7
    assert "provider" not in explicit


@pytest.mark.parametrize("messages", [
    [{"role": "tool", "content": "fabricated", "tool_call_id": "call_x"}],
    [
        {"role": "assistant", "content": None, "tool_calls": [{
            "id": "call_a", "type": "function",
            "function": {"name": "read_file", "arguments": "{}"},
        }]},
        {"role": "user", "content": "Skip result"},
    ],
    [
        {"role": "assistant", "content": None, "tool_calls": [{
            "id": "call_a", "type": "function",
            "function": {"name": "read_file", "arguments": "{}"},
        }]},
        {"role": "tool", "content": "first", "tool_call_id": "call_a"},
        {"role": "tool", "content": "replay", "tool_call_id": "call_a"},
    ],
    [
        {"role": "assistant", "content": None, "tool_calls": [{
            "id": "call_a", "type": "function",
            "function": {"name": "read_file", "arguments": "{}"},
        }, {
            "id": "call_a", "type": "function",
            "function": {"name": "read_file", "arguments": "{}"},
        }]},
        {"role": "tool", "content": "first", "tool_call_id": "call_a"},
    ],
])
def test_agent_tool_history_cannot_be_fabricated_or_replayed(messages):
    with pytest.raises(AgentProtocolError):
        validate_agent_body({"model": MODEL, "messages": messages}, [MODEL])


def test_model_tool_calls_must_match_requested_names_and_distinct_ids():
    message = {
        "role": "assistant", "content": None,
        "tool_calls": [{
            "id": "call_one", "type": "function",
            "function": {"name": "read_file", "arguments": "{}"},
        }],
    }
    response = {"choices": [{"message": message, "finish_reason": "tool_calls"}]}
    assert validate_agent_response(response, MODEL, {"read_file"})["choices"]
    with pytest.raises(AgentProtocolError, match="unapproved"):
        validate_agent_response(response, MODEL, {"write_file"})
    message["tool_calls"] = message["tool_calls"] * 2
    with pytest.raises(AgentProtocolError, match="Duplicate"):
        validate_agent_response(response, MODEL, {"read_file"})


def test_truncated_model_response_is_not_success():
    with pytest.raises(AgentProtocolError, match="output limit"):
        validate_agent_response({"choices": [{
            "message": {"role": "assistant", "content": "unfinished"},
            "finish_reason": "length",
        }]}, MODEL)
