"""Regression tests for transactional outcome infrastructure classification.

Run from api/: python -m unittest discover -s tests -p 'test_transactional_outcome_sqlite.py'
"""
import hashlib
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

from agent_platform.evals.transactional_outcome_prototype import initialize, verify_and_record
from agent_platform.evals.trusted_receipt_prototype import issue


class TransactionalOutcomeSQLiteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = str(self.root / "receipts.sqlite")
        self.db = sqlite3.connect(self.path, timeout=0.02)
        self.addCleanup(self.db.close)
        initialize(self.db)
        data = b"verified output"
        (self.root / "result.txt").write_bytes(data)
        self.key = b"k" * 32
        self.receipt = issue(self.key, {
            "version": 1, "issuer": "trusted-sandbox-runner-v1",
            "task_id": "task", "run_id": "run", "nonce": "nonce",
            "issued_at": 1000, "expires_at": 1100,
            "artifacts": {"result.txt": hashlib.sha256(data).hexdigest()},
        })

    def verify(self, db=None, receipt=None):
        return verify_and_record(
            db if db is not None else self.db, self.key,
            receipt if receipt is not None else self.receipt,
            self.root, task_id="task", run_id="run", now=1050,
        )

    def test_verified_then_idempotent_replay(self):
        self.assertEqual(self.verify(), "verified")
        self.assertEqual(self.verify(), "already_verified")

    def test_invalid_mac_is_rejected(self):
        bad = dict(self.receipt, mac="0" * 64)
        self.assertEqual(self.verify(receipt=bad), "rejected")

    def test_lock_is_infrastructure_error_and_retry_succeeds(self):
        blocker = sqlite3.connect(self.path, timeout=0.02)
        self.addCleanup(blocker.close)
        blocker.execute("BEGIN IMMEDIATE")
        contender = sqlite3.connect(self.path, timeout=0.02)
        self.addCleanup(contender.close)
        self.assertEqual(self.verify(db=contender), "infrastructure_error")
        self.assertFalse(contender.in_transaction)
        blocker.rollback()
        self.assertEqual(self.verify(db=contender), "verified")

    def test_caller_transaction_is_not_rolled_back(self):
        self.db.execute("BEGIN")
        self.assertEqual(self.verify(), "infrastructure_error")
        self.assertTrue(self.db.in_transaction)
        self.db.rollback()
        self.assertEqual(self.verify(), "verified")

    def v2_receipt(self, nonce, attempt_id):
        return issue(self.key, dict(self.receipt["payload"], version=2, nonce=nonce, attempt_id=attempt_id))

    def test_v2_same_attempt_different_nonces_rejected(self):
        self.assertEqual(self.verify(receipt=self.v2_receipt("first", "attempt-1")), "verified")
        self.assertEqual(self.verify(receipt=self.v2_receipt("second", "attempt-1")), "rejected")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM verified_outcomes").fetchone()[0], 1)
        self.assertEqual(self.verify(receipt=self.v2_receipt("first", "attempt-1")), "already_verified")

    def test_v2_concurrent_nonces_one_verified(self):
        # Two independent connections race to consume the same signed attempt.
        # The unique attempt index must make the outcome exactly one success.
        barrier = threading.Barrier(3)
        outcomes = []
        errors = []
        lock = threading.Lock()

        def worker(nonce):
            try:
                connection = sqlite3.connect(self.path, timeout=2.0)
                try:
                    barrier.wait(timeout=3)
                    result = self.verify(db=connection, receipt=self.v2_receipt(nonce, "race-attempt"))
                    with lock:
                        outcomes.append(result)
                finally:
                    connection.close()
            except Exception as exc:
                with lock:
                    errors.append(repr(exc))

        threads = [threading.Thread(target=worker, args=(nonce,)) for nonce in ("race-a", "race-b")]
        for thread in threads:
            thread.start()
        barrier.wait(timeout=3)
        for thread in threads:
            thread.join(timeout=5)
        self.assertFalse(any(thread.is_alive() for thread in threads), "verification threads must terminate")
        self.assertEqual(errors, [])
        self.assertCountEqual(outcomes, ["verified", "rejected"])
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM verified_outcomes").fetchone()[0], 1)

    def test_v2_distinct_attempts_allowed(self):
        self.assertEqual(self.verify(receipt=self.v2_receipt("first", "attempt-1")), "verified")
        self.assertEqual(self.verify(receipt=self.v2_receipt("second", "attempt-2")), "verified")

    def test_v2_invalid_attempt_identity_rejected(self):
        for attempt in ("", "x" * 129, None):
            self.assertEqual(self.verify(receipt=self.v2_receipt("nonce-" + str(attempt), attempt)), "rejected")

    def test_v2_existing_schema_migrates(self):
        legacy = sqlite3.connect(":memory:")
        self.addCleanup(legacy.close)
        legacy.execute("CREATE TABLE verified_outcomes (issuer TEXT NOT NULL, nonce TEXT NOT NULL, task_id TEXT NOT NULL, run_id TEXT NOT NULL, receipt_hash TEXT NOT NULL, manifest TEXT NOT NULL, PRIMARY KEY(issuer, nonce))")
        initialize(legacy)
        self.assertEqual(self.verify(db=legacy, receipt=self.v2_receipt("first", "attempt-1")), "verified")
        self.assertEqual(self.verify(db=legacy, receipt=self.v2_receipt("second", "attempt-1")), "rejected")

    def test_missing_schema_is_infrastructure_error(self):
        other = sqlite3.connect(":memory:")
        self.addCleanup(other.close)
        self.assertEqual(self.verify(db=other), "infrastructure_error")


if __name__ == "__main__":
    unittest.main()
