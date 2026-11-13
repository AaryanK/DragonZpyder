"""Diagnostic regression: different valid nonces for one task/run are not deduplicated.

This is an expected failure until an authoritative attempt identity exists.
Do not 'fix' by enforcing task/run uniqueness: authorized reruns need distinct attempts.
"""
import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path

from agent_platform.evals.trusted_receipt_prototype import issue
from agent_platform.evals.transactional_outcome_prototype import initialize, verify_and_record


class AttemptIdentityContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "report.txt").write_bytes(b"verified artifact")
        self.db = sqlite3.connect(self.root / "outcomes.db")
        self.addCleanup(self.db.close)
        initialize(self.db)
        self.key = b"k" * 32
        self.payload = dict(
            version=1, issuer="trusted-sandbox-runner-v1",
            task_id="task", run_id="run", nonce="nonce-a",
            issued_at=100, expires_at=200,
            artifacts={"report.txt": hashlib.sha256(b"verified artifact").hexdigest()},
        )

    def record(self, nonce):
        payload = dict(self.payload, nonce=nonce)
        return verify_and_record(
            self.db, self.key, issue(self.key, payload), self.root,
            task_id="task", run_id="run", now=150,
        )

    @unittest.expectedFailure
    def test_one_logical_attempt_cannot_be_verified_twice_with_different_nonces(self):
        """Known gap: no trusted attempt_id in receipt or ledger yet."""
        self.assertEqual(self.record("nonce-a"), "verified")
        self.assertNotEqual(self.record("nonce-b"), "verified")

    def test_same_receipt_retry_remains_idempotent(self):
        self.assertEqual(self.record("nonce-a"), "verified")
        self.assertEqual(self.record("nonce-a"), "already_verified")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM verified_outcomes").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
