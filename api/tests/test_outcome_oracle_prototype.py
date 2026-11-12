import hashlib
import tempfile
import unittest
from pathlib import Path

from agent_platform.evals.outcome_oracle_prototype import verify_artifacts


class OracleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "result.txt").write_bytes(b"correct")
        self.expected = {"result.txt": hashlib.sha256(b"correct").hexdigest()}
        self.receipt = {"run_id": "run-123", "artifacts": self.expected.copy()}

    def tearDown(self):
        self.tmp.cleanup()

    def check(self):
        return verify_artifacts(self.root, "run-123", self.receipt, self.expected)

    def test_success(self):
        self.assertTrue(self.check())

    def test_wrong_run(self):
        self.receipt["run_id"] = "run-999"
        self.assertFalse(self.check())

    def test_forged_digest(self):
        self.receipt["artifacts"] = {"result.txt": "0" * 64}
        self.assertFalse(self.check())

    def test_modified_bytes(self):
        (self.root / "result.txt").write_bytes(b"changed")
        self.assertFalse(self.check())

    def test_missing_file(self):
        (self.root / "result.txt").unlink()
        self.assertFalse(self.check())

    def test_traversal(self):
        d = {"../outside": "0" * 64}
        self.assertFalse(verify_artifacts(self.root, "run-123", {"run_id": "run-123", "artifacts": d}, d))

    def test_symlink(self):
        (self.root / "result.txt").unlink()
        (self.root / "result.txt").symlink_to("/etc/hosts")
        self.assertFalse(self.check())

    def test_extra_artifact(self):
        self.receipt["artifacts"]["extra"] = "0" * 64
        self.assertFalse(self.check())

    def test_empty_expected(self):
        self.assertFalse(verify_artifacts(self.root, "run-123", {"run_id": "run-123", "artifacts": {}}, {}))

    def test_nonhex_digest(self):
        d = {"result.txt": "z" * 64}
        self.assertFalse(verify_artifacts(self.root, "run-123", {"run_id": "run-123", "artifacts": d}, d))
