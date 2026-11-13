import os
import sqlite3
import tempfile
import unittest
from api.agent_platform.evals.trusted_receipt_prototype import initialize, issue, verify_once

KEY = b"K" * 32
BASE = {"version": 1, "issuer": "trusted-sandbox-runner-v1", "task_id": "task-1", "run_id": "run-1", "nonce": "nonce-1", "issued_at": 100, "expires_at": 200, "artifacts": {"result.txt": "a" * 64}}

class ReceiptSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, "replay.sqlite")
        self.db = sqlite3.connect(self.path)
        initialize(self.db)
    def tearDown(self):
        self.db.close()
        self.temp.cleanup()
    def verify(self, payload=None, *, task="task-1", run="run-1", now=150, key=KEY):
        return verify_once(self.db, KEY, issue(key, BASE if payload is None else payload), task_id=task, run_id=run, now=now)
    def test_accept_once(self):
        self.assertTrue(self.verify())
        self.assertFalse(self.verify())
    def test_restart_replay(self):
        self.assertTrue(self.verify())
        self.db.close()
        self.db = sqlite3.connect(self.path)
        initialize(self.db)
        self.assertFalse(self.verify())
    def test_wrong_key(self):
        self.assertFalse(self.verify(key=b"Z" * 32))
    def test_wrong_task(self):
        self.assertFalse(self.verify(task="task-2"))
    def test_wrong_run(self):
        self.assertFalse(self.verify(run="run-2"))
    def test_expired(self):
        self.assertFalse(self.verify(now=200))
    def test_future(self):
        self.assertFalse(self.verify(now=99))
    def test_long_ttl(self):
        self.assertFalse(self.verify(dict(BASE, expires_at=500)))
    def test_invalid_digest(self):
        self.assertFalse(self.verify(dict(BASE, artifacts={"result.txt": "bad"})))
    def test_bool_timestamp(self):
        self.assertFalse(self.verify(dict(BASE, issued_at=True)))
    def test_cross_run_nonce_reuse(self):
        self.assertTrue(self.verify())
        self.assertFalse(self.verify(dict(BASE, run_id="run-2"), run="run-2"))
    def test_path_traversal(self):
        self.assertFalse(self.verify(dict(BASE, artifacts={"../outside.txt": "a" * 64})))
    def test_absolute_path(self):
        self.assertFalse(self.verify(dict(BASE, artifacts={"/etc/passwd": "a" * 64})))
    def test_dot_component(self):
        self.assertFalse(self.verify(dict(BASE, artifacts={"sub/./file": "a" * 64})))
    def test_empty_component(self):
        self.assertFalse(self.verify(dict(BASE, artifacts={"sub//file": "a" * 64})))
    def test_nul_path(self):
        self.assertFalse(self.verify(dict(BASE, artifacts={"file\x00name": "a" * 64})))
    def test_valid_nested(self):
        self.assertTrue(self.verify(dict(BASE, artifacts={"sub/file": "a" * 64})))
    def test_forged_payload(self):
        r = issue(KEY, BASE)
        r["payload"] = dict(BASE, task_id="task-2")
        self.assertFalse(verify_once(self.db, KEY, r, task_id="task-2", run_id="run-1", now=150))

if __name__ == "__main__":
    unittest.main()
