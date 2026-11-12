"""Fail-closed, pure verification of sandbox artifact digests.

This does not authenticate sandbox receipts. The trusted runner must supply
the expected run ID and artifact digests out of band.
"""
import hashlib
import hmac
from pathlib import Path


def verify_artifacts(root: Path, expected_run_id: str, receipt: dict, expected: dict[str, str]) -> bool:
    """Check run binding, exact artifact set, path containment and SHA-256 bytes."""
    if not isinstance(receipt, dict) or not isinstance(expected_run_id, str) or not expected_run_id:
        return False
    if receipt.get("run_id") != expected_run_id or not isinstance(expected, dict) or not expected:
        return False
    if receipt.get("artifacts") != expected:
        return False
    try:
        base = root.resolve(strict=True)
        for name, digest in expected.items():
            if not isinstance(name, str) or not name or name.startswith("/") or "\\" in name:
                return False
            parts = Path(name).parts
            if any(p in ("..", ".") for p in parts) or not isinstance(digest, str) or len(digest) != 64:
                return False
            bytes.fromhex(digest)
            path = base.joinpath(*parts)
            if any(p.is_symlink() for p in [path, *list(path.parents)[:len(parts)-1]]):
                return False
            resolved = path.resolve(strict=True)
            if not resolved.is_relative_to(base) or not resolved.is_file():
                return False
            actual = hashlib.sha256(resolved.read_bytes()).hexdigest()
            if not hmac.compare_digest(actual, digest.lower()):
                return False
        return True
    except (OSError, ValueError, TypeError):
        return False
