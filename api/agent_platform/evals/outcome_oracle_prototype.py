"""Bounded artifact verification. Receipts are NOT authenticated by this module.

Expected digests and run IDs must originate from a trusted runner, not the agent.
"""
import hashlib
import hmac
import os
import stat
from pathlib import Path

MAX_ARTIFACTS = 32
MAX_ARTIFACT_BYTES = 64 * 1024 * 1024
CHUNK_BYTES = 1024 * 1024


def verify_artifacts(root: Path, expected_run_id: str, receipt: dict, expected: dict[str, str]) -> bool:
    """Check exact artifact bytes using bounded, no-follow descriptor traversal."""
    if not isinstance(receipt, dict) or not isinstance(expected_run_id, str) or not expected_run_id:
        return False
    if receipt.get("run_id") != expected_run_id or not isinstance(expected, dict) or not 0 < len(expected) <= MAX_ARTIFACTS:
        return False
    if receipt.get("artifacts") != expected:
        return False
    root_fd = None
    try:
        root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        for name, digest in expected.items():
            if not isinstance(name, str) or not name or name.startswith("/") or "\\" in name or "\x00" in name:
                return False
            parts = name.split("/")
            if any(part in ("", ".", "..") for part in parts):
                return False
            if not isinstance(digest, str) or len(digest) != 64:
                return False
            try:
                bytes.fromhex(digest)
            except ValueError:
                return False
            opened = []
            try:
                parent_fd = root_fd
                for part in parts[:-1]:
                    fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
                    opened.append(fd)
                    parent_fd = fd
                fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent_fd)
                opened.append(fd)
                info = os.fstat(fd)
                if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_ARTIFACT_BYTES:
                    return False
                digest_state = hashlib.sha256()
                count = 0
                while True:
                    chunk = os.read(fd, min(CHUNK_BYTES, MAX_ARTIFACT_BYTES - count + 1))
                    if not chunk:
                        break
                    count += len(chunk)
                    if count > MAX_ARTIFACT_BYTES:
                        return False
                    digest_state.update(chunk)
                if not hmac.compare_digest(digest_state.hexdigest(), digest.lower()):
                    return False
            finally:
                for fd in reversed(opened):
                    os.close(fd)
        return True
    except (OSError, ValueError, TypeError, OverflowError):
        return False
    finally:
        if root_fd is not None:
            os.close(root_fd)
