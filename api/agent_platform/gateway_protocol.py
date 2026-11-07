"""Bounded OpenAI-compatible TOOL-CALLING protocol for internal agents.

No tool is ever executed by this gateway. It only transports function calls
between a registered agent service and an allowlisted OpenRouter model.
"""
from __future__ import annotations

import json
import math
import re
from typing import Any


class AgentProtocolError(ValueError):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]{0,79}$")
_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def _reject(message: str, status: int = 400):
    raise AgentProtocolError(status, message)


def _bounded_text(value: Any, *, limit: int = 30000, nullable: bool = False):
    if nullable and value is None:
        return None
    # LangChain's OpenAI client can send text-only content as structured blocks.
    # Flatten text blocks, but reject image/audio/file or arbitrary object blocks.
    if isinstance(value, list):
        if not 1 <= len(value) <= 12:
            _reject("Unsupported message content")
        text_parts = []
        for item in value:
            if (not isinstance(item, dict) or item.get("type") != "text"
                    or not isinstance(item.get("text"), str)):
                _reject("Unsupported nontext message block")
            text_parts.append(item["text"])
        value = "\n".join(text_parts)
    if not isinstance(value, str) or len(value) > limit:
        _reject("Unsupported message content")
    return value


def _tool_call(value: Any) -> dict:
    if not isinstance(value, dict) or value.get("type") != "function":
        _reject("Invalid tool call")
    if not isinstance(value.get("id"), str) or not _ID.fullmatch(value["id"]):
        _reject("Invalid tool call ID")
    fn = value.get("function")
    if not isinstance(fn, dict) or not isinstance(fn.get("name"), str) or not _NAME.fullmatch(fn["name"]):
        _reject("Invalid tool call function")
    arguments = _bounded_text(fn.get("arguments"), limit=32000)
    try:
        parsed = json.loads(arguments)
    except (ValueError, TypeError):
        _reject("Tool call arguments must be JSON")
    if not isinstance(parsed, dict):
        _reject("Tool call arguments must be a JSON object")
    return {"id": value["id"], "type": "function", "function": {
        "name": fn["name"], "arguments": arguments,
    }}


def _tools(value: Any) -> list:
    if not isinstance(value, list) or not 1 <= len(value) <= 16:
        _reject("Invalid tool count")
    out = []
    seen = set()
    for tool in value:
        if not isinstance(tool, dict) or tool.get("type") != "function":
            _reject("Only function tools are allowed")
        fn = tool.get("function")
        if not isinstance(fn, dict) or not isinstance(fn.get("name"), str) or not _NAME.fullmatch(fn["name"]):
            _reject("Invalid tool name")
        if fn["name"] in seen:
            _reject("Duplicate tool name")
        seen.add(fn["name"])
        desc = _bounded_text(fn.get("description") or "", limit=8000)
        schema = fn.get("parameters", {"type": "object", "properties": {}})
        if not isinstance(schema, dict) or schema.get("type") != "object":
            _reject("Function parameters must be a JSON object schema")
        if len(json.dumps(schema, separators=(",", ":"))) > 12000:
            _reject("Function schema is too large", 413)
        out.append({"type": "function", "function": {
            "name": fn["name"], "description": desc, "parameters": schema,
        }})
    return out


def validate_agent_body(value: Any, allowed_models: list[str]) -> dict:
    if not isinstance(value, dict):
        _reject("Invalid JSON request")
    model = value.get("model")
    if not isinstance(model, str) or model not in allowed_models:
        _reject("Model is not in the agent gateway allowlist", 403)
    messages = value.get("messages")
    if not isinstance(messages, list) or not 1 <= len(messages) <= 60:
        _reject("Invalid message count")
    sanitized = []
    total = 0
    for item in messages:
        if not isinstance(item, dict):
            _reject("Invalid message")
        role = item.get("role")
        if role not in {"system", "developer", "user", "assistant", "tool"}:
            _reject("Invalid message role")
        content = _bounded_text(item.get("content"), nullable=role == "assistant")
        total += len(content or "")
        clean = {"role": role, "content": content}
        if role == "tool":
            call_id = item.get("tool_call_id")
            if not isinstance(call_id, str) or not _ID.fullmatch(call_id):
                _reject("Tool response must reference a tool call ID")
            clean["tool_call_id"] = call_id
        elif role == "assistant" and "tool_calls" in item:
            calls = item["tool_calls"]
            if not isinstance(calls, list) or not 1 <= len(calls) <= 12:
                _reject("Invalid assistant tool call count")
            clean["tool_calls"] = [_tool_call(call) for call in calls]
            total += sum(len(call["function"]["arguments"]) for call in clean["tool_calls"])
        sanitized.append(clean)
    if total > 125000:
        _reject("Agent conversation exceeds input budget", 413)
    tokens = value.get("max_tokens", value.get("max_completion_tokens", 1200))
    if type(tokens) is not int or not 1 <= tokens <= 4096:
        _reject("Invalid output token limit")
    if value.get("stream") is not False and value.get("stream") is not None:
        _reject("Streaming is not enabled for agent gateway")
    temperature = value.get("temperature", 0.2)
    if type(temperature) not in (float, int) or not math.isfinite(temperature) or not 0 <= temperature <= 1.5:
        _reject("Invalid temperature")
    body = {"model": model, "messages": sanitized, "max_tokens": tokens,
            "temperature": temperature, "stream": False}
    if "tools" in value:
        body["tools"] = _tools(value["tools"])
    if "tool_choice" in value:
        choice = value["tool_choice"]
        if choice in ("auto", "none", "required"):
            body["tool_choice"] = choice
        elif (isinstance(choice, dict) and choice.get("type") == "function" and
              isinstance(choice.get("function"), dict) and
              isinstance(choice["function"].get("name"), str) and
              _NAME.fullmatch(choice["function"]["name"])):
            body["tool_choice"] = {"type": "function", "function": {
                "name": choice["function"]["name"],
            }}
        else:
            _reject("Invalid tool choice")
    if "parallel_tool_calls" in value:
        if type(value["parallel_tool_calls"]) is not bool:
            _reject("Invalid parallel_tool_calls")
        body["parallel_tool_calls"] = value["parallel_tool_calls"]
    return body


def validate_agent_response(provider_response: Any, requested_model: str) -> dict:
    if not isinstance(provider_response, dict):
        _reject("Invalid model response", 502)
    choices = provider_response.get("choices")
    if not isinstance(choices, list) or not choices:
        _reject("Missing model choice", 502)
    choice = choices[0]
    message = choice.get("message") if isinstance(choice, dict) else None
    if not isinstance(message, dict) or message.get("role") != "assistant":
        _reject("Invalid model message", 502)
    content = _bounded_text(message.get("content"), limit=90000, nullable=True)
    out_message = {"role": "assistant", "content": content}
    if message.get("tool_calls") is not None:
        calls = message["tool_calls"]
        if not isinstance(calls, list) or not 1 <= len(calls) <= 12:
            _reject("Invalid model tool calls", 502)
        try:
            out_message["tool_calls"] = [_tool_call(call) for call in calls]
        except AgentProtocolError:
            _reject("Invalid model tool call format", 502)
    elif content is None:
        _reject("Missing model content", 502)
    return {
        "id": str(provider_response.get("id") or ""),
        "object": "chat.completion",
        "model": str(provider_response.get("model") or requested_model),
        "choices": [{"index": 0, "message": out_message,
                     "finish_reason": choice.get("finish_reason") or "stop"}],
        **({"usage": provider_response["usage"]} if isinstance(provider_response.get("usage"), dict) else {}),
    }
