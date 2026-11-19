"""Zero-cost subprocess characterization of crash-after-effect replay risk.

Not a test of DragonZpyder's production runtime. Uses isolated temp files.
"""
import sqlite3
import subprocess
import sys

WORKER = r'''
import sqlite3, os, sys
from pathlib import Path
root = Path(sys.argv[1]); phase = sys.argv[2]
conn = sqlite3.connect(root / 'operations.sqlite')
conn.execute('CREATE TABLE IF NOT EXISTS operations (id TEXT PRIMARY KEY, state TEXT NOT NULL)')
conn.commit()
row = conn.execute('SELECT state FROM operations WHERE id=?', ('send',)).fetchone()
if row is None:
    conn.execute('INSERT INTO operations VALUES (?,?)', ('send','inflight'))
    conn.commit()
elif row[0] == 'confirmed':
    sys.exit(0)
with (root / 'external-effects.log').open('a') as f:
    f.write('send\n'); f.flush(); os.fsync(f.fileno())
if phase == 'crash':
    os._exit(17)
conn.execute('UPDATE operations SET state=? WHERE id=?', ('confirmed','send'))
conn.commit()
'''


def test_naive_retry_duplicates_external_effect_after_crash(tmp_path):
    first = subprocess.run([sys.executable, '-c', WORKER, str(tmp_path), 'crash'], check=False)
    assert first.returncode == 17
    db = sqlite3.connect(tmp_path / 'operations.sqlite')
    assert db.execute('SELECT state FROM operations').fetchone() == ('inflight',)
    db.close()
    second = subprocess.run([sys.executable, '-c', WORKER, str(tmp_path), 'retry'], check=False)
    assert second.returncode == 0
    assert (tmp_path / 'external-effects.log').read_text().splitlines() == ['send', 'send']


def test_uncertain_nonidempotent_action_must_not_be_blindly_retried(tmp_path):
    first = subprocess.run([sys.executable, '-c', WORKER, str(tmp_path), 'crash'], check=False)
    assert first.returncode == 17
    db = sqlite3.connect(tmp_path / 'operations.sqlite')
    state = db.execute('SELECT state FROM operations').fetchone()[0]
    db.close()
    decision = 'reconcile_or_human_review' if state == 'inflight' else 'execute'
    assert decision == 'reconcile_or_human_review'
    assert (tmp_path / 'external-effects.log').read_text().splitlines() == ['send']


# Reference recovery policy, not a production dispatcher.
SAFE_WORKER = r'''
import sqlite3, os, sys
from pathlib import Path
root = Path(sys.argv[1]); phase = sys.argv[2]
conn = sqlite3.connect(root / 'operations.sqlite')
conn.execute('CREATE TABLE IF NOT EXISTS operations (id TEXT PRIMARY KEY, state TEXT NOT NULL)')
conn.commit()
conn.execute('BEGIN IMMEDIATE')
row = conn.execute('SELECT state FROM operations WHERE id=?', ('send',)).fetchone()
if row is not None:
    conn.rollback()
    sys.exit(0 if row[0] == 'confirmed' else 23)
conn.execute('INSERT INTO operations VALUES (?, ?)', ('send', 'inflight'))
conn.commit()
with (root / 'external-effects.log').open('a') as f:
    f.write('send\n'); f.flush(); os.fsync(f.fileno())
if phase == 'crash':
    os._exit(17)
conn.execute('UPDATE operations SET state=? WHERE id=?', ('confirmed', 'send'))
conn.commit()
'''


def test_fail_closed_restart_does_not_duplicate_uncertain_effect(tmp_path):
    first = subprocess.run([sys.executable, '-c', SAFE_WORKER, str(tmp_path), 'crash'], check=False)
    assert first.returncode == 17
    second = subprocess.run([sys.executable, '-c', SAFE_WORKER, str(tmp_path), 'retry'], check=False)
    assert second.returncode == 23  # reconciliation required
    assert (tmp_path / 'external-effects.log').read_text().splitlines() == ['send']
    with sqlite3.connect(tmp_path / 'operations.sqlite') as conn:
        assert conn.execute('SELECT state FROM operations WHERE id=?', ('send',)).fetchone() == ('inflight',)
