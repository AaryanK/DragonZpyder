"""Native Hatchet canary contract: no Operly or paid model required."""
import asyncio
import os
from pathlib import Path
import sys
from unittest.mock import patch
from uuid import uuid4
import json

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_platform.native_canary import (
    NativeCanaryWake, TOOL_ARGS, native_canary_tools, require_native_canary,
)
from agent_platform.scientific_oracles import check_quadratic_gradient_step


def test_signed_canary_tools_do_not_expose_other_users():
    user_id, conversation_id = str(uuid4()), str(uuid4())
    tools = native_canary_tools(user_id=user_id, conversation_id=conversation_id)
    assert [x.name for x in tools] == [
        "native_canary_start", "native_canary_status", "native_canary_cancel"
    ]
    for t in tools:
        schema = t.args_schema.model_json_schema()
        assert "user_id" not in schema["properties"]
        assert "conversation_id" not in schema["properties"]


def test_invalid_identity_and_canary_sequence_rejected():
    from pydantic import ValidationError
    with pytest.raises(ValueError, match="Canonical"):
        native_canary_tools(user_id="not-a-uuid", conversation_id=str(uuid4()))
    with pytest.raises(ValidationError):
        NativeCanaryWake(goal_id=str(uuid4()), sequence=2)


def test_worker_canary_flag_and_db_are_required():
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(RuntimeError, match="disabled"):
            require_native_canary()
    with patch.dict(os.environ, {"DRAGONZPYDER_NATIVE_CANARY_ENABLED": "1"},
                    clear=True):
        with pytest.raises(RuntimeError, match="PostgreSQL"):
            require_native_canary()
    with patch.dict(os.environ, {
        "DRAGONZPYDER_NATIVE_CANARY_ENABLED": "1",
        "DRAGONZPYDER_PERSONAL_MCP_DATABASE_URL": "postgresql://example/canary",
        "DRAGONZPYDER_AGENT_DATABASE_URL": "postgresql://example/other",
    }, clear=True):
        assert require_native_canary() == "postgresql://example/canary"


def test_canary_uses_production_builtin_math_tool():
    output = asyncio.run(check_quadratic_gradient_step.ainvoke(TOOL_ARGS))
    result = json.loads(output)
    assert result["arithmetic_valid"] is True
    assert result["gradient"] == "2.00"
    assert result["expected_next"] == "1.800"
