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
