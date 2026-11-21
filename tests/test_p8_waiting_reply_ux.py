from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout

from dragonzpyder.cli import _print_task


class WaitingReplyUxTests(unittest.TestCase):
    def test_waiting_invitation_is_presented_as_wait_not_blocker(self):
        output = io.StringIO()
        with redirect_stdout(output):
            _print_task(
                {
                    "status": "waiting_event",
                    "task_id": "personal-task:fixture",
                    "current_step_id": "recheck",
                    "checkpoint_version": 3,
                    "deadline_at": "2026-09-23T09:00:00+00:00",
                    "wait_predicate": {
                        "kind": "gmail_thread_reply",
                        "expected_sender": "alex@example.test",
                    },
                    "error_code": "waiting_for_invitation_reply",
                    "error": "Waiting for a verified reply from the invited recipient",
                }
            )
        rendered = output.getvalue()
        self.assertIn("Status: waiting_event", rendered)
        self.assertIn("Waiting for reply from alex@example.test.", rendered)
        self.assertIn("Reply deadline: 2026-09-23T09:00:00+00:00", rendered)
        self.assertIn("do not submit a duplicate booking task", rendered)
        self.assertNotIn("Blocker: waiting_for_invitation_reply", rendered)


if __name__ == "__main__":
    unittest.main()
