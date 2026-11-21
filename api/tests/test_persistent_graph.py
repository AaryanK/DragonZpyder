"""Contract tests for signed, finite multi-tool execution graphs."""
import sys
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_platform.persistent_graph import (
    GraphStep, GraphWake, validate_plan, graph_tools, _compose, _verify, _sha,
)


def steps():
    return [
        GraphStep(id="workflows",kind="mcp_read",capability_id="workflow.list"),
        GraphStep(id="tasks",kind="mcp_read",capability_id="tasks.list"),
        GraphStep(id="report",kind="compose",depends_on=["workflows","tasks"]),
        GraphStep(id="verify",kind="verify",depends_on=["report"]),
    ]


def test_two_distinct_read_tools_and_dependency_plan():
    plan=validate_plan(steps())
    assert len(plan)==4
    assert plan[2]["depends_on"]==["workflows","tasks"]
    assert plan[3]["kind"]=="verify"


@pytest.mark.parametrize("mutation",[
    lambda s: setattr(s[0],"capability_id","workspace.create"),
    lambda s: setattr(s[0],"arguments",{"foo":"bar"}),
    lambda s: setattr(s[1],"depends_on",["workflows"]),
    lambda s: setattr(s[2],"depends_on",["workflows"]),
    lambda s: setattr(s[2],"id","workflows"),
    lambda s: setattr(s[3],"depends_on",["tasks"]),
    lambda s: setattr(s[1],"capability_id","workflow.list"),
])
def test_malformed_or_mutating_graph_fails_before_dispatch(mutation):
    plan=steps()
    mutation(plan)
    with pytest.raises(ValueError):
        validate_plan(plan)


def test_user_ids_not_model_arguments():
    bound=graph_tools(user_id=str(uuid4()),session_id=str(uuid4()),
                      conversation_id=str(uuid4()))
    assert [x.name for x in bound]==[
        "graph_schedule","graph_status","graph_cancel"]
    args=bound[0].args_schema.model_json_schema()["properties"]
    for forbidden in ("user_id","session_id","conversation_id","access_token"):
        assert forbidden not in args
    with pytest.raises(ValueError,match="Canonical"):
        graph_tools(user_id="not-a-uuid",session_id=str(uuid4()),
                    conversation_id=str(uuid4()))


def test_report_roundtrip_verification():
    data={"result":{"workflows":[]}}
    other={"result":{"tasks":[]}}
    sources={
        "workflows":{"data":data,"hash":_sha(data),"tool":"operly_workflow_list"},
        "tasks":{"data":other,"hash":_sha(other),"tool":"operly_tasks_list"},
    }
    compose=steps()[2]
    artifact=_compose(str(uuid4()),compose,sources)
    assert artifact["source_count"]==2
    sources["report"]={"data":artifact,"hash":_sha(artifact),
                       "tool":"native_graph_compose"}
    verified=_verify(steps()[3],sources)
    assert verified["verified"] is True
    sources["tasks"]["data"]={"result":{"tasks":[1]}}
    with pytest.raises(ValueError,match="integrity"):
        _verify(steps()[3],sources)


def test_worker_input_cannot_substitute_authority():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        GraphWake(goal_id=str(uuid4()),sequence=10)
    with pytest.raises(ValidationError):
        GraphWake(goal_id=str(uuid4()),sequence=0,user_id=str(uuid4()))


def test_graph_feature_gate_is_off_by_default():
    from agent_platform.persistent_graph import require_graph_gate
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(RuntimeError,match="disabled"):
            require_graph_gate()
