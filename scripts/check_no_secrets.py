from __future__ import annotations

import pathlib
import re
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "build",
    "dist",
    "__pycache__",
    ".pytest_cache",
}
TEXT_SUFFIXES = {
    "",
    ".py",
    ".md",
    ".json",
    ".toml",
    ".yml",
    ".yaml",
    ".txt",
    ".example",
    ".gitignore",
}

PATTERNS = {
    "twilio_account_sid": re.compile(r"\bAC[0-9a-fA-F]{32}\b"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "literal_secret_assignment": re.compile(
        r"(?i)\b(?:auth_token|api_key|client_secret|password|access_token)\s*=\s*['\"][^'\"]{12,}['\"]"
    ),
}


def candidate_files():
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        if path.name == ".env.example" or path.suffix in TEXT_SUFFIXES:
            yield path


def main() -> int:
    findings: list[tuple[str, int, str]] = []
    for path in candidate_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            for name, pattern in PATTERNS.items():
                if pattern.search(line):
                    findings.append((str(path.relative_to(ROOT)), line_no, name))

    if findings:
        for path, line_no, name in findings:
            print(f"secret-pattern finding: {path}:{line_no}: {name}", file=sys.stderr)
        return 1

    print("current-tree secret-pattern scan passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
