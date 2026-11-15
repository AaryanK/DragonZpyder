"""Isolated transactional artifact-outcome verifier; not a runner attestation.

No external side effects are executed here. Files must be immutable during verification;
callers must isolate artifact roots from untrusted writers before invoking this.
"""
import hashlib
import hmac
import sqlite3
import time
from pathlib import Path

from agent_platform.evals.outcome_oracle_prototype import verify_artifacts
from agent_platform.evals.trusted_receipt_prototype import canonical, MAX_TTL_SECONDS


def initialize(db):
    db.execute('CREATE TABLE IF NOT EXISTS verified_outcomes (issuer TEXT NOT NULL, nonce TEXT NOT NULL, task_id TEXT NOT NULL, run_id TEXT NOT NULL, receipt_hash TEXT NOT NULL, manifest TEXT NOT NULL, PRIMARY KEY(issuer, nonce))')
    # Additive migration: legacy v1 receipts retain nonce-only semantics.
    cols = {row[1] for row in db.execute('PRAGMA table_info(verified_outcomes)')}
    if 'attempt_id' not in cols:
        db.execute('ALTER TABLE verified_outcomes ADD COLUMN attempt_id TEXT')
    db.execute('CREATE UNIQUE INDEX IF NOT EXISTS verified_attempt_identity ON verified_outcomes (issuer, task_id, run_id, attempt_id) WHERE attempt_id IS NOT NULL')
    db.commit()


def verify_and_record(db: sqlite3.Connection, key: bytes, receipt: dict, root: Path, *, task_id: str, run_id: str, now=None, require_v2: bool = False):
    """Return 'verified', 'already_verified', 'rejected', or 'infrastructure_error'.

    Set require_v2=True for trusted callers that have migrated to signed\n    logical-attempt identities; legacy receipts are rejected before DB access.\n    SQLite transaction binds nonce consumption to durable verification outcome.
    This is a local single-DB prototype, not a distributed exactly-once protocol.
    """
    try:
        if type(require_v2) is not bool:
            return 'rejected'
        if not isinstance(key, bytes) or len(key) < 32 or not isinstance(receipt, dict):
            return 'rejected'
        p = receipt['payload']
        base_fields = {'version','issuer','task_id','run_id','nonce','issued_at','expires_at','artifacts'}
        if not isinstance(p, dict) or type(p.get('version')) is not int or p['version'] not in (1, 2):
            return 'rejected'
        if require_v2 and p['version'] != 2:
            return 'rejected'
        if set(p) != (base_fields if p['version'] == 1 else base_fields | {'attempt_id'}):
            return 'rejected'
        if p['issuer'] != 'trusted-sandbox-runner-v1':
            return 'rejected'
        if not all(isinstance(x, str) and x for x in (task_id, run_id, p['nonce'])) or p['task_id'] != task_id or p['run_id'] != run_id:
            return 'rejected'
        # v2 binds a trusted logical attempt to the signed receipt. v1 remains
        # readable for compatibility, but cannot provide attempt deduplication.
        attempt_id = p.get('attempt_id') if p['version'] == 2 else None
        if p['version'] == 2 and (not isinstance(attempt_id, str) or not attempt_id or len(attempt_id) > 128):
            return 'rejected'
        mac = receipt['mac']
        if not isinstance(mac, str) or len(mac) != 64 or not hmac.compare_digest(hmac.new(key, canonical(p), hashlib.sha256).hexdigest(), mac):
            return 'rejected'
        if type(p['issued_at']) is not int or type(p['expires_at']) is not int or not 0 < p['expires_at']-p['issued_at'] <= MAX_TTL_SECONDS:
            return 'rejected'
        t = int(time.time()) if now is None else now
        if type(t) is not int:
            return 'rejected'
        manifest = p['artifacts']
        if not isinstance(manifest, dict) or not 0 < len(manifest) <= 32:
            return 'rejected'
        for name, digest in manifest.items():
            if not isinstance(name,str) or not name or name.startswith('/') or '\\' in name or '\x00' in name or any(s in ('','.','..') for s in name.split('/')):
                return 'rejected'
            if not isinstance(digest,str) or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):
                return 'rejected'
        receipt_hash = hashlib.sha256(canonical(p)).hexdigest()
        manifest_json = canonical(manifest).decode('ascii')
        db.execute('BEGIN IMMEDIATE')
        try:
            existing = db.execute('SELECT task_id,run_id,receipt_hash,manifest FROM verified_outcomes WHERE issuer=? AND nonce=?', (p['issuer'],p['nonce'])).fetchone()
            if existing:
                db.rollback()
                return 'already_verified' if existing == (task_id,run_id,receipt_hash,manifest_json) else 'rejected'
            if attempt_id is not None:
                # Under BEGIN IMMEDIATE, a competing nonce for the same signed
                # logical attempt cannot both commit.
                prior = db.execute('SELECT nonce FROM verified_outcomes WHERE issuer=? AND task_id=? AND run_id=? AND attempt_id=?', (p['issuer'], task_id, run_id, attempt_id)).fetchone()
                if prior:
                    db.rollback()
                    return 'rejected'
            if not p['issued_at'] <= t < p['expires_at']:
                db.rollback()
                return 'rejected'
            if not verify_artifacts(root, run_id, {'run_id':run_id,'artifacts':manifest}, manifest):
                db.rollback()
                return 'rejected'
            db.execute('INSERT INTO verified_outcomes (issuer,nonce,task_id,run_id,receipt_hash,manifest,attempt_id) VALUES (?,?,?,?,?,?,?)', (p['issuer'],p['nonce'],task_id,run_id,receipt_hash,manifest_json,attempt_id))
            db.commit()
            return 'verified'
        except Exception:
            db.rollback()
            raise
    except sqlite3.Error:
        # Database availability/transaction failures are not invalid receipts.
        # BEGIN IMMEDIATE can fail before the inner rollback scope; do not
        # rollback a transaction owned by the caller.
        return 'infrastructure_error'
    except (KeyError,TypeError,ValueError,OverflowError):
        return 'rejected'


def check_delivery_availability(db: sqlite3.Connection, root: Path, *, issuer: str, nonce: str, task_id: str, run_id: str) -> str:
    """Recheck current artifact bytes without changing historical verification.

    Returns 'available', 'unavailable', or 'unknown'. This is a point-in-time
    check, not a storage lease: delivery must pin/copy immutable bytes itself.
    The caller must authorize access to this outcome and artifact root.
    """
    if not all(isinstance(v, str) and v for v in (issuer, nonce, task_id, run_id)):
        return 'unknown'
    try:
        row = db.execute(
            'SELECT manifest FROM verified_outcomes WHERE issuer=? AND nonce=? AND task_id=? AND run_id=?',
            (issuer, nonce, task_id, run_id),
        ).fetchone()
        if row is None:
            return 'unknown'
        import json
        manifest = json.loads(row[0])
        if not isinstance(manifest, dict):
            return 'unavailable'
        return 'available' if verify_artifacts(root, run_id, {'run_id': run_id, 'artifacts': manifest}, manifest) else 'unavailable'
    except (sqlite3.Error, ValueError, TypeError, OSError):
        return 'unknown'
