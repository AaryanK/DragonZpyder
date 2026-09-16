from __future__ import annotations

from contextlib import redirect_stdout
import io
import unittest

from dragonzpyder.cli import _error
from dragonzpyder.client import (
    ClientResponse,
    DragonZpyderClient,
    DragonZpyderClientError,
)
from dragonzpyder.config import DragonZpyderConfig


class FakeTransport:
    def __init__(self, responses) -> None:
        self.responses = list(responses)
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
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return ClientResponse(status=200, payload=response)

    def clear(self):
        pass


def client_with(responses) -> tuple[DragonZpyderClient, FakeTransport]:
    transport = FakeTransport(responses)
    return (
        DragonZpyderClient(
            DragonZpyderConfig("https://operly.example.test"),
            transport=transport,
        ),
        transport,
    )


APPROVED = {
    "id": "approval-send-1",
    "status": "approved",
    "capability_id": "google.gmail.send_email",
    "request_id": "send-request-1",
    "conversation_id": "conversation-1",
    "arguments": {
        "to": ["alex@example.test"],
        "cc": [],
        "bcc": [],
        "subject": "Tuesday at 2?",
        "text_body": "Hi Alex,\n\nWould Tuesday at 2:00 PM work for you?",
    },
}


class P6SendFlowTests(unittest.TestCase):
    def test_approve_executes_exact_server_returned_contract(self):
        result = {
            "status": "completed",
            "result": {
                "message_id": "gmail-1",
                "verification_status": "read_back",
            },
        }
        client, transport = client_with([APPROVED, result])

        approved, executed = client.approve_and_execute("approval-send-1")

        self.assertEqual(approved["status"], "approved")
        self.assertEqual(executed["result"]["message_id"], "gmail-1")
        self.assertEqual(
            [call["path"] for call in transport.calls],
            [
                "/api/personal-tools/approvals/approval-send-1/decision",
                "/api/personal-tools/google.gmail.send_email/execute",
            ],
        )
        execution = transport.calls[1]
        self.assertEqual(execution["payload"]["arguments"], APPROVED["arguments"])
        self.assertEqual(execution["payload"]["request_id"], "send-request-1")
        self.assertEqual(execution["payload"]["approval_id"], "approval-send-1")
        self.assertEqual(execution["payload"]["conversation_id"], "conversation-1")
        self.assertNotIn("workspace_id", execution["payload"])
        self.assertTrue(execution["csrf"])
        self.assertTrue(execution["authenticated"])

    def test_resume_approved_recovers_after_decision_execute_gap(self):
        result = {"status": "completed", "result": {"message_id": "gmail-2"}}
        client, transport = client_with(
            [
                {"approvals": [APPROVED]},
                result,
            ]
        )

        executed = client.resume_approved("approval-send-1")

        self.assertEqual(executed["result"]["message_id"], "gmail-2")
        self.assertEqual(transport.calls[0]["path"], "/api/personal-tools/approvals")
        self.assertEqual(
            transport.calls[1]["path"],
            "/api/personal-tools/google.gmail.send_email/execute",
        )

    def test_uncertain_send_is_not_presented_as_retryable(self):
        error = DragonZpyderClientError(
            "Gmail delivery is uncertain",
            code="execution_outcome_uncertain",
            status=409,
            retryable=False,
            details={
                "rfc822_message_id": "<operly-fixture@operly.invalid>",
                "recovery": "search_sent_mail_by_rfc822_message_id_before_retry",
            },
        )
        output = io.StringIO()
        with redirect_stdout(output):
            code = _error(error, request_id="send-request-1")

        rendered = output.getvalue()
        self.assertEqual(code, 5)
        self.assertIn("Stable message identity: <operly-fixture@operly.invalid>", rendered)
        self.assertIn("Do not send again", rendered)
        self.assertIn("search_sent_mail_by_rfc822_message_id_before_retry", rendered)
        self.assertNotIn("Retry with the same request ID", rendered)


if __name__ == "__main__":
    unittest.main()
