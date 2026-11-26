#!/usr/bin/env python3
"""Require a new explicit codebase change record for each changed non-doc path."""
import argparse
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = "docs/codebase/CHANGES.md"
RECORD = re.compile(r"^\+[-*] \x60([^\x60]+)\x60:\s*(\S.*)$")

def git(root, *args):
    return subprocess.check_output(["git", *args], cwd=root)

def missing_records(root, base, head="HEAD"):
    changed = git(root, "diff", "--name-only", "--no-renames", "-z", base + "..." + head)
    paths = {os.fsdecode(p) for p in changed.split(b"\0") if p}
    patch = git(root, "diff", "--no-ext-diff", "--unified=0", base + "..." + head, "--", LEDGER).decode("utf-8")
    records = {m.group(1) for line in patch.splitlines() if (m := RECORD.match(line)) and len(m.group(2).strip()) >= 20}
    return sorted(p for p in paths if not p.lower().endswith((".md", ".rst", ".adoc")) and p not in records)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", default="HEAD")
    args = parser.parse_args()
    missing = missing_records(ROOT, args.base, args.head)
    if missing:
        print("Add a new path-specific record to " + LEDGER + ":")
        for p in missing:
            print(" - " + p)
        raise SystemExit(1)
    print("Documentation records cover all changed non-documentation paths.")

if __name__ == "__main__":
    main()
