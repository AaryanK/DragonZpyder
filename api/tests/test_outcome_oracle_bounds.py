"""Adversarial bounds and descriptor traversal regression tests."""
import hashlib
import os
import tempfile
import unittest
from pathlib import Path

from agent_platform.evals.outcome_oracle_prototype import MAX_ARTIFACT_BYTES, verify_artifacts


class BoundedOracleTests(unittest.TestCase):
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

    def test_nested_valid(self):
        (self.root / "nested").mkdir()
        (self.root / "nested" / "a").write_bytes(b"ok")
        self.expected = {"nested/a": hashlib.sha256(b"ok").hexdigest()}
        self.receipt["artifacts"] = self.expected.copy()
        self.assertTrue(self.check())

    def test_nested_symlink(self):
        (self.root / "nested").symlink_to("/etc")
        self.expected = {"nested/hosts": hashlib.sha256(b"ok").hexdigest()}
        self.receipt["artifacts"] = self.expected.copy()
        self.assertFalse(self.check())

    def test_fifo(self):
        (self.root / "result.txt").unlink()
        os.mkfifo(self.root / "result.txt")
        self.assertFalse(self.check())

    def test_oversize(self):
        with (self.root / "result.txt").open("wb") as f:
            f.truncate(MAX_ARTIFACT_BYTES + 1)
        self.assertFalse(self.check())

    def test_too_many(self):
        self.expected = {f"a{i}": "0" * 64 for i in range(33)}
        self.receipt["artifacts"] = self.expected.copy()
        self.assertFalse(self.check())

    def test_empty_segment(self):
        self.expected = {"nested//a": "0" * 64}
        self.receipt["artifacts"] = self.expected.copy()
        self.assertFalse(self.check())


if __name__ == "__main__":
    unittest.main()
