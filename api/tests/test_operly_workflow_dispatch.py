"""No-network contracts for the shared Hatchet business dispatch adapter."""
import asyncio
import os
from pathlib import Path
import sys
from unittest.mock import AsyncMock, patch

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_platform.operly_workflow_dispatch import (
    CRON_NAME, PATH, WorkflowPulseInput, dispatch_pulse,
    install_workflow_cron, require_dispatch_gate,
)

SECRET = "dispatch-test-" + "x" * 40
ENV = {
    "DRAGONZPYDER_OPERLY_WORKFLOW_DISPATCH_ENABLED": "1",
    "DRAGONZPYDER_OPERLY_WORKFLOW_DISPATCH_SECRET": SECRET,
}


def test_default_disabled_and_arbitrary_endpoints_rejected():
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(RuntimeError, match="disabled"):
            require_dispatch_gate()
    for url in ("https://example.com" + PATH,
                "https://operly.dragonzpyder.xyz/mcp",
                "http://operly.dragonzpyder.xyz" + PATH):
        with patch.dict(os.environ, {**ENV,
                        "DRAGONZPYDER_OPERLY_WORKFLOW_DISPATCH_URL": url}, clear=True):
            with pytest.raises(RuntimeError, match="configuration"):
                require_dispatch_gate()
    with patch.dict(os.environ, {**ENV,
                    "DRAGONZPYDER_OPERLY_MCP_SERVICE_SECRET": SECRET}, clear=True):
        with pytest.raises(RuntimeError, match="independent"):
            require_dispatch_gate()


def test_operator_pulse_uses_no_model_no_user_context():
    observed = []
    async def run():
        def handler(request):
            observed.append(request)
            return httpx.Response(200, json={
                "state":"dispatched", "claimed_runs":2, "event_runs_queued":3,
                "private_details":"do not propagate",
            })
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await dispatch_pulse(client=client)
    with patch.dict(os.environ, ENV, clear=True):
        assert asyncio.run(run()) == {
            "state":"dispatched", "claimed_runs":2, "event_runs_queued":3,
        }
    assert len(observed) == 1
    request = observed[0]
    assert request.url.path == PATH
    assert request.headers["X-DragonZpyder-Workflow-Dispatch"] == SECRET
    assert request.content == b""


@pytest.mark.parametrize("status,body", [
    (409, {"state":"dispatched","claimed_runs":0,"event_runs_queued":0}),
    (200, {"state":"completed","claimed_runs":1,"event_runs_queued":0}),
    (200, {"state":"busy","claimed_runs":1,"event_runs_queued":0}),
    (200, {"state":"dispatched","claimed_runs":True,"event_runs_queued":0}),
    (200, {"state":"dispatched","claimed_runs":26,"event_runs_queued":0}),
])
def test_rejected_or_malformed_wakes_fail_closed(status,body):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(
                lambda _: httpx.Response(status,json=body))) as client:
            await dispatch_pulse(client=client)
    with patch.dict(os.environ, ENV, clear=True):
        with pytest.raises(RuntimeError):
            asyncio.run(run())


def test_cron_install_is_separate_explicit_operation():
    class Task:
        aio_create_cron = AsyncMock(return_value={"ok":True})
    task=Task()
    with patch.dict(os.environ, ENV, clear=True):
        with pytest.raises(RuntimeError, match="authorized"):
            asyncio.run(install_workflow_cron(task))
    task.aio_create_cron.assert_not_called()
    with patch.dict(os.environ, {**ENV,
                    "DRAGONZPYDER_OPERLY_WORKFLOW_CRON_INSTALL_ALLOWED":"1"}, clear=True):
        asyncio.run(install_workflow_cron(task))
    task.aio_create_cron.assert_awaited_once_with(
        cron_name=CRON_NAME, expression="* * * * *", input=WorkflowPulseInput(),
    )


def test_model_cannot_inject_arbitrary_dispatch_arguments():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        WorkflowPulseInput(user_id="other-user", capability="tasks.create")
