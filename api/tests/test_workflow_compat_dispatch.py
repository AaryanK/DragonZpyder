"""No-credit contracts for the temporary first-party workflow dispatcher."""
import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_platform.workflow_compat_dispatch import (
    CRON_NAME, ENDPOINT, DispatchInput, dispatch_compatibility_tick,
    install_compatibility_cron,
)

ENV = {
    "DRAGONZPYDER_OPERLY_WORKFLOW_HANDOFF_ENABLED": "1",
    "DRAGONZPYDER_OPERLY_WORKFLOW_HANDOFF_SECRET": "x" * 48,
}
RECEIPT = {
    "driver": "dragonzpyder", "dispatch": "accepted",
    "queued_events": 2, "active_workers": 1, "completion_verified": False,
}


def test_default_closed_without_network():
    with patch.dict("os.environ", {}, clear=True):
        client = AsyncMock()
        with pytest.raises(RuntimeError, match="disabled"):
            asyncio.run(dispatch_compatibility_tick(client=client))
        client.post.assert_not_awaited()


def test_exact_service_route_and_dispatch_receipt():
    async def run():
        def handle(request):
            assert str(request.url) == ENDPOINT
            assert request.method == "POST"
            assert request.headers["X-DragonZpyder-Workflow-Proof"] == ENV[
                "DRAGONZPYDER_OPERLY_WORKFLOW_HANDOFF_SECRET"]
            assert not request.content
            return httpx.Response(200, json={**RECEIPT, "unreviewed": "not returned"})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            return await dispatch_compatibility_tick(client=client)
    with patch.dict("os.environ", ENV, clear=True):
        assert asyncio.run(run()) == RECEIPT


@pytest.mark.parametrize("status,body", [
    (302, RECEIPT), (403, RECEIPT), (503, RECEIPT),
    (200, {**RECEIPT, "completion_verified": True}),
    (200, {**RECEIPT, "queued_events": False}),
    (200, {**RECEIPT, "active_workers": -1}),
    (200, {"dispatch": "accepted"}),
])
def test_reject_failed_or_untrustworthy_receipt(status, body):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(
            lambda _: httpx.Response(status, json=body, headers={"Location": "https://example.invalid"})
        )) as client:
            return await dispatch_compatibility_tick(client=client)
    with patch.dict("os.environ", ENV, clear=True):
        with pytest.raises(RuntimeError, match="workflow_handoff_"):
            asyncio.run(run())


def test_explicit_cron_install_gate():
    task = AsyncMock()
    with patch.dict("os.environ", ENV, clear=True):
        with pytest.raises(RuntimeError, match="cron_install_not_approved"):
            asyncio.run(install_compatibility_cron(task))
        task.aio_create_cron.assert_not_awaited()
    with patch.dict("os.environ", {**ENV,
            "DRAGONZPYDER_WORKFLOW_HANDOFF_CRON_INSTALL_ALLOWED": "1"}, clear=True):
        asyncio.run(install_compatibility_cron(task))
        task.aio_create_cron.assert_awaited_once_with(
            cron_name=CRON_NAME, expression="* * * * *", input=DispatchInput(),
        )


def test_task_input_cannot_inject_credentials_or_scope():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        DispatchInput(user_id="some-user", url="https://example.invalid")
