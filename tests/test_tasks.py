from __future__ import annotations

import unittest

from dragonzpyder.client import ClientResponse, DragonZpyderClient
from dragonzpyder.config import DragonZpyderConfig
from dragonzpyder.tasks import (
    approve_and_resume_durable_task,
    cancel_durable_task,
    durable_task_status,
    resume_durable_task,
    submit_durable_task,
)


class FakeTransport:
    def __init__(self, responses=None) -> None:
        self.responses = list(responses or [])
        self.calls: list[dict] = []

    def request_json(self, method, path, payload=None, *, csrf=False, authenticated=False):
        self.calls.append(
            {
                "method": method,
                "path": path,
                "payload": payload,
                "csrf": csrf,
                "authenticated": authenticated,
            }
        )
        if not self.responses:
            raise AssertionError(f"Unexpected request: {method} {path}")
        return ClientResponse(status=200, payload=self.responses.pop(0))

    def clear(self):
        pass


def client_with(transport: FakeTransport) -> DragonZpyderClient:
    return DragonZpyderClient(
        DragonZpyderConfig("https://operly.example.test"),
        transport=transport,
    )


class DurableTaskClientTests(unittest.TestCase):
    def test_submit_uses_stable_personal_task_contract_without_workspace_authority(self):
        transport = FakeTransport(
            [
                {
                    "task_id": "personal-task:abc",
                    "status": "queued",
                    "conversation_id": "conversation-1",
                    "client_request_id": "durable-001",
                }
            ]
        )
        result = submit_durable_task(
            client_with(transport),
            "Find an afternoon next week when I am free.",
            request_id="durable-001",
            max_steps=6,
            max_mutations=2,
        )
        self.assertEqual(result["status"], "queued")
        call = transport.calls[0]
        self.assertEqual(call["method"], "POST")
        self.assertEqual(call["path"], "/api/personal-tools/client/tasks")
        self.assertEqual(call["payload"]["request_id"], "durable-001")
        self.assertEqual(call["payload"]["max_steps"], 6)
        self.assertEqual(call["payload"]["max_mutations"], 2)
        self.assertNotIn("workspace_id", call["payload"])
        self.assertNotIn("selected_workspace_id", call["payload"])
        self.assertTrue(call["csrf"])
        self.assertTrue(call["authenticated"])

    def test_status_and_cancel_use_server_owned_task_identity(self):
        transport = FakeTransport(
            [
                {"task_id": "personal-task:abc", "status": "running"},
                {"task_id": "personal-task:abc", "status": "cancelled"},
            ]
        )
        client = client_with(transport)
        status = durable_task_status(client, "personal-task:abc")
        cancelled = cancel_durable_task(client, "personal-task:abc")
        self.assertEqual(status["status"], "running")
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertEqual(
            [call["path"] for call in transport.calls],
            [
                "/api/personal-tools/client/tasks/personal-task%3Aabc",
                "/api/personal-tools/client/tasks/personal-task%3Aabc/cancel",
            ],
        )
        self.assertFalse(transport.calls[0]["csrf"])
        self.assertTrue(transport.calls[1]["csrf"])

    def test_resume_passes_only_exact_server_approval_reference(self):
        transport = FakeTransport(
            [{"task_id": "personal-task:abc", "status": "queued"}]
        )
        result = resume_durable_task(
            client_with(transport),
            "personal-task:abc",
            approval_id="11111111-1111-1111-1111-111111111111",
        )
        self.assertEqual(result["status"], "queued")
        call = transport.calls[0]
        self.assertEqual(
            call["payload"],
            {"approval_id": "11111111-1111-1111-1111-111111111111"},
        )
        self.assertNotIn("capability_id", call["payload"])
        self.assertNotIn("arguments", call["payload"])

    def test_task_approval_does_not_execute_capability_from_client(self):
        approval_id = "11111111-1111-1111-1111-111111111111"
        transport = FakeTransport(
            [
                {"id": approval_id, "status": "approved"},
                {
                    "task_id": "personal-task:abc",
                    "status": "queued",
                    "approval_id": approval_id,
                },
            ]
        )
        result = approve_and_resume_durable_task(
            client_with(transport),
            "personal-task:abc",
            approval_id,
        )
        self.assertEqual(result["status"], "queued")
        self.assertEqual(
            [call["path"] for call in transport.calls],
            [
                f"/api/personal-tools/approvals/{approval_id}/decision",
                "/api/personal-tools/client/tasks/personal-task%3Aabc/resume",
            ],
        )
        self.assertFalse(
            any("/execute" in call["path"] for call in transport.calls),
            "durable task approval must return execution to Operly's worker",
        )


if __name__ == "__main__":
    unittest.main()
