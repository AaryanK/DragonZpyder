"""Isolated receipt authentication prototype; NOT proof of sandbox execution."""
import hashlib
import hmac
import json
import sqlite3
import time

MAX_TTL_SECONDS = 300
MAX_ARTIFACTS = 32

def canonical(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()

def issue(key, payload):
    if not isinstance(key, bytes) or len(key) < 32 or not isinstance(payload, dict):
        raise ValueError("invalid key or payload")
    return {"payload": payload, "mac": hmac.new(key, canonical(payload), hashlib.sha256).hexdigest()}

def initialize(db):
    db.execute("CREATE TABLE IF NOT EXISTS consumed_receipts (issuer TEXT NOT NULL, nonce TEXT NOT NULL, task_id TEXT NOT NULL, run_id TEXT NOT NULL, PRIMARY KEY (issuer, nonce))")
    db.commit()

def verify_once(db: sqlite3.Connection, key: bytes, receipt: dict, *, task_id: str, run_id: str, now=None):
    """Consume a valid receipt once in shared durable SQLite.

    Caller MUST independently verify artifacts and atomically bind the outcome.
    The HMAC key MUST be controlled exclusively by the trusted runner.
    """
    try:
        if not isinstance(key, bytes) or len(key) < 32 or not isinstance(receipt, dict):
            return False
        p = receipt["payload"]
        if not isinstance(p, dict) or set(p) != {"version", "issuer", "task_id", "run_id", "nonce", "issued_at", "expires_at", "artifacts"}:
            return False
        if type(p["version"]) is not int or p["version"] != 1 or p["issuer"] != "trusted-sandbox-runner-v1":
            return False
        if p["task_id"] != task_id or p["run_id"] != run_id or not all(isinstance(x, str) and x for x in (task_id, run_id, p["nonce"])):
            return False
        if type(p["issued_at"]) is not int or type(p["expires_at"]) is not int:
            return False
        t = int(time.time()) if now is None else now
        if type(t) is not int or not p["issued_at"] <= t < p["expires_at"] or not 0 < p["expires_at"] - p["issued_at"] <= MAX_TTL_SECONDS:
            return False
        artifacts = p["artifacts"]
        if not isinstance(artifacts, dict) or not 0 < len(artifacts) <= MAX_ARTIFACTS:
            return False
        for name, digest in artifacts.items():
            if (not isinstance(name, str) or not name or name.startswith("/") or "\\" in name or "\x00" in name
                or any(part in ("", ".", "..") for part in name.split("/"))):
                return False
            if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
                return False
        mac = receipt["mac"]
        if not isinstance(mac, str) or len(mac) != 64 or not hmac.compare_digest(hmac.new(key, canonical(p), hashlib.sha256).hexdigest(), mac):
            return False
        db.execute("BEGIN IMMEDIATE")
        try:
            db.execute("INSERT INTO consumed_receipts (issuer, nonce, task_id, run_id) VALUES (?,?,?,?)", (p["issuer"], p["nonce"], task_id, run_id))
            db.commit()
            return True
        except sqlite3.IntegrityError:
            db.rollback()
            return False
        except Exception:
            db.rollback()
            raise
    except (KeyError, TypeError, ValueError, OverflowError, sqlite3.Error):
        return False
