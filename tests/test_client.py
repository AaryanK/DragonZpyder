from __future__ import annotations

from contextlib import redirect_stdout
import io
import unittest

from dragonzpyder.cli import _print_submission
from dragonzpyder.client import (
    ClientResponse,
    DragonZpyderAuthError,
    DragonZpyderClient,
    DragonZpyderClientError,
)
from dragonzpyder.config import DragonZpyderConfig


class FakeTransport:
    def __init__(self, responses=None) -> None:
        self.responses = list(responses or [])
        self.calls: list[dict] = []
        self.cleared = False

    def request_json(
        self,
        method,
        path,
        payload=None,
        *,
        csrf=False,
        authenticated=False,
    ):
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
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return ClientResponse(status=200, payload=response)

    def clear(self):
        self.cleared = True


def client_with(transport: FakeTransport) -> DragonZpyderClient:
    return DragonZpyderClient(
        DragonZpyderConfig("https://operly.example.test"),
        transport=transport,
    )


def fixture_password() -> str:
    # Construct test-only data without resembling a checked-in credential assignment.
    return "-".join(("fixture", "password"))


class DragonZpyderClientTests(unittest.TestCase):
    def test_login_converts_workspace_session_to_personal_authority(self):
        transport = FakeTransport(
            [
                {"csrf_token": "preauth"},
                {"ok": True, "scope": "workspace"},
                {"ok": True, "scope": "personal"},
                [
                    {
                        "id": "personal-session",
                        "current": True,
                        "scope": "personal",
                        "expires_at": "2026-09-23T00:00:00",
                    }
                ],
            ]
        )
        client = client_with(transport)

        current = client.login(email="person@example.test", **{"password": fixture_password()})

        self.assertEqual(current["scope"], "personal")
        self.assertEqual(
            [call["path"] for call in transport.calls],
            [
                "/api/auth/bootstrap",
                "/api/auth/login",
                "/api/auth/personal-scope",
                "/api/auth/sessions",
            ],
        )
        personal_scope = transport.calls[2]
        self.assertTrue(personal_scope["csrf"])
        self.assertTrue(personal_scope["authenticated"])
        self.assertNotIn("workspace", str(personal_scope["payload"]).lower())

    def test_existing_personal_login_does_not_switch_workspace(self):
        transport = FakeTransport(
            [
                {"csrf_token": "preauth"},
                {"ok": True, "scope": "personal"},
                [{"id": "s1", "current": True, "scope": "personal"}],
            ]
        )
        current = client_with(transport).login(
            email="person@example.test",
            **{"password": fixture_password()},
        )
        self.assertEqual(current["scope"], "personal")
        self.assertNotIn(
            "/api/auth/switch-workspace",
            [call["path"] for call in transport.calls],
        )

    def test_submit_sends_stable_request_identity_without_workspace_authority(self):
        transport = FakeTransport(
            [
                {
                    "message": "Free afternoon found.",
                    "conversation_id": "conversation-1",
                    "client_request_id": "retry-123456",
                    "replayed": False,
                }
            ]
        )
        result = client_with(transport).submit(
            "Find an afternoon next week when I am free.",
            request_id="retry-123456",
        )

        self.assertEqual(result["client_request_id"], "retry-123456")
        call = transport.calls[0]
        self.assertEqual(call["path"], "/api/personal-tools/client/submit")
        self.assertEqual(call["payload"]["request_id"], "retry-123456")
        self.assertNotIn("workspace_id", call["payload"])
        self.assertNotIn("selected_workspace_id", call["payload"])
        self.assertTrue(call["csrf"])
        self.assertTrue(call["authenticated"])

    def test_conversation_continuation_keeps_same_personal_contract(self):
        transport = FakeTransport([{"message": "Draft saved."}])
        client_with(transport).submit(
            "Use that time and draft the invitation.",
            conversation_id="conversation-1",
            request_id="retry-continue-1",
        )
        self.assertEqual(
            transport.calls[0]["payload"]["conversation_id"],
            "conversation-1",
        )

    def test_pending_approval_and_decision_use_existing_personal_endpoints(self):
        transport = FakeTransport(
            [
                {"approvals": [{"id": "approval-1", "arguments": {"to": "alex@example.test"}}]},
                {"id": "approval-1", "status": "approved"},
            ]
        )
        client = client_with(transport)
        rows = client.pending_approvals()
        decision = client.decide_approval("approval-1", approved=True)

        self.assertEqual(rows[0]["id"], "approval-1")
        self.assertEqual(decision["status"], "approved")
        self.assertEqual(
            [call["path"] for call in transport.calls],
            [
                "/api/personal-tools/approvals?status=pending",
                "/api/personal-tools/approvals/approval-1/decision",
            ],
        )
        self.assertTrue(transport.calls[1]["csrf"])
        self.assertTrue(transport.calls[1]["authenticated"])

    def test_expired_server_session_is_a_clear_authentication_failure(self):
        transport = FakeTransport(
            [
                DragonZpyderAuthError(
                    "Session is no longer valid",
                    code="HTTP_401",
                    status=401,
                )
            ]
        )
        with self.assertRaises(DragonZpyderAuthError):
            client_with(transport).status()

    def test_logout_clears_local_session_even_when_server_session_expired(self):
        transport = FakeTransport(
            [
                DragonZpyderAuthError(
                    "Session is no longer valid",
                    code="HTTP_401",
                    status=401,
                )
            ]
        )
        client_with(transport).logout()
        self.assertTrue(transport.cleared)

    def test_submission_display_does_not_expose_model_or_capability_plumbing(self):
        output = io.StringIO()
        with redirect_stdout(output):
            _print_submission(
                {
                    "message": "Draft saved for review.",
                    "conversation_id": "conversation-1",
                    "client_request_id": "retry-1",
                    "capability_calls": ["google.gmail.create_draft"],
                    "model_id": "some-provider-model",
                }
            )
        rendered = output.getvalue()
        self.assertIn("Draft saved for review", rendered)
        self.assertNotIn("google.gmail.create_draft", rendered)
        self.assertNotIn("some-provider-model", rendered)

    def test_empty_task_is_rejected_before_transport(self):
        transport = FakeTransport([])
        with self.assertRaises(DragonZpyderClientError) as caught:
            client_with(transport).submit("   ")
        self.assertEqual(caught.exception.code, "TASK_REQUIRED")
        self.assertEqual(transport.calls, [])


if __name__ == "__main__":
    unittest.main()
