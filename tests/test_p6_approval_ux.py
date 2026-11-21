from __future__ import annotations

from contextlib import redirect_stdout
import io
import unittest

from dragonzpyder.cli import _print_approvals


class P6ApprovalUxTests(unittest.TestCase):
    def test_approval_output_shows_exact_review_content_hash_and_expiry(self):
        output = io.StringIO()
        with redirect_stdout(output):
            _print_approvals(
                (
                    {
                        "id": "approval-send-1",
                        "status": "pending",
                        "arguments": {
                            "to": ["alex@example.test"],
                            "cc": [],
                            "bcc": [],
                            "subject": "Tuesday at 2?",
                            "text_body": "Hi Alex,\n\nWould Tuesday at 2:00 PM work for you?",
                        },
                        "arguments_hash": "a" * 64,
                        "expires_at": "2026-09-16T02:45:00",
                    },
                )
            )

        rendered = output.getvalue()
        self.assertIn("exact reviewed content", rendered)
        self.assertIn("alex@example.test", rendered)
        self.assertIn("Tuesday at 2?", rendered)
        self.assertIn("Would Tuesday at 2:00 PM work for you?", rendered)
        self.assertIn("Review hash: " + "a" * 64, rendered)
        self.assertIn("Approval expires: 2026-09-16T02:45:00", rendered)
        self.assertIn("Decision: pending", rendered)


if __name__ == "__main__":
    unittest.main()
