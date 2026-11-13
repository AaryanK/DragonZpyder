import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path

from agent_platform.evals.trusted_receipt_prototype import issue
from agent_platform.evals.transactional_outcome_prototype import initialize, verify_and_record


class TransactionalOutcomeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.dbpath = self.root / "outcomes.db"
        self.db = sqlite3.connect(self.dbpath)
        self.addCleanup(lambda: self.db.close())
        initialize(self.db)
        self.key = b"k" * 32
        (self.root / "report.txt").write_bytes(b"correct")
        self.payload = dict(version=1, issuer="trusted-sandbox-runner-v1",
                            task_id="t", run_id="r", nonce="n",
                            issued_at=100, expires_at=200,
                            artifacts={"report.txt": hashlib.sha256(b"correct").hexdigest()})

    def check(self, payload=None, now=150):
        return verify_and_record(self.db, self.key, issue(self.key, payload or self.payload),
                                 self.root, task_id="t", run_id="r", now=now)

    def test_success_and_idempotent_retry(self):
        self.assertEqual(self.check(), "verified")
        self.assertEqual(self.check(), "already_verified")

    def test_missing_artifact_does_not_consume(self):
        (self.root / "report.txt").unlink()
        self.assertEqual(self.check(), "rejected")
        self.assertEqual(self.db.execute("SELECT count(*) FROM verified_outcomes").fetchone()[0], 0)
        (self.root / "report.txt").write_bytes(b"correct")
        self.assertEqual(self.check(), "verified")

    def test_wrong_bytes(self):
        (self.root / "report.txt").write_bytes(b"wrong")
        self.assertEqual(self.check(), "rejected")

    def test_restart_after_commit(self):
        self.assertEqual(self.check(), "verified")
        self.db.close()
        self.db = sqlite3.connect(self.dbpath)
        self.assertEqual(self.check(), "already_verified")

    def test_expired_unconsumed(self):
        self.assertEqual(self.check(now=201), "rejected")

    def test_conflicting_nonce(self):
        self.assertEqual(self.check(), "verified")
        p = dict(self.payload, artifacts={"report.txt": "0" * 64})
        self.assertEqual(self.check(p), "rejected")

    def test_cross_run(self):
        self.assertEqual(self.check(dict(self.payload, run_id="other")), "rejected")

    def test_path_traversal(self):
        p = dict(self.payload, artifacts={"../report.txt": self.payload["artifacts"]["report.txt"]})
        self.assertEqual(self.check(p), "rejected")

    def test_symlink(self):
        (self.root / "report.txt").unlink()
        (self.root / "report.txt").symlink_to("/etc/hosts")
        self.assertEqual(self.check(), "rejected")

    def test_delivery_availability_after_delete_and_replace(self):
        from agent_platform.evals.transactional_outcome_prototype import check_delivery_availability
        self.assertEqual(self.check(), 'verified')
        args = dict(issuer='trusted-sandbox-runner-v1', nonce='n', task_id='t', run_id='r')
        self.assertEqual(check_delivery_availability(self.db, self.root, **args), 'available')
        (self.root / 'report.txt').unlink()
        self.assertEqual(check_delivery_availability(self.db, self.root, **args), 'unavailable')
        self.assertEqual(self.check(), 'already_verified')
        (self.root / 'report.txt').write_bytes(b'wrong')
        self.assertEqual(check_delivery_availability(self.db, self.root, **args), 'unavailable')
        (self.root / 'report.txt').write_bytes(b'correct')
        self.assertEqual(check_delivery_availability(self.db, self.root, **args), 'available')

    def test_delivery_availability_rejects_unknown_identity(self):
        from agent_platform.evals.transactional_outcome_prototype import check_delivery_availability
        self.assertEqual(self.check(), 'verified')
        args = dict(issuer='trusted-sandbox-runner-v1', nonce='n', task_id='t', run_id='r')
        self.assertEqual(check_delivery_availability(self.db, self.root, **dict(args, task_id='other')), 'unknown')
        self.assertEqual(check_delivery_availability(self.db, self.root, **dict(args, nonce='other')), 'unknown')


if __name__ == "__main__":
    unittest.main()
