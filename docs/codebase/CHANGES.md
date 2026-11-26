# Codebase change records

For each implementation change, add a new bullet beginning with the exact repository-relative path in backticks, followed by a colon and a substantive explanation. Include changed behavior or why behavior is unchanged, affected callers/dependencies, constraints, tests/evidence and unresolved limitations. Record both paths for a rename; describe removals. Do not edit old entries to make a new change appear covered. Update file inventory, local guides and execution flows alongside this record. Documentation-only edits need no records.

## 2026-11-26 — documentation infrastructure

- `scripts/build_codebase_index.py`: Generates source-derived file and directory pages and flat navigation, extracts symbols, docstrings, parameters, call candidates, imports, routes and candidate references; includes curated purpose rows; no application execution. Initial generator and gate passed the codebase documentation CI; expanded coverage checks require their own run.
- `scripts/check_codebase_docs.py`: Compares base and head; requires a new record naming every changed non-documentation path, including both old/new paths on rename; checks exact tracked inventory and folder guides. Structural check, not semantic certification.
- `tests/test_codebase_documentation.py`: Offline temporary-repository fixtures for extraction, reference hints, generated pages and change-record validation.
- `.github/workflows/codebase-docs.yml`: Read-only CI builds/uploads the index and checks path-specific records on PRs; no deployment or automatic branch writes.
