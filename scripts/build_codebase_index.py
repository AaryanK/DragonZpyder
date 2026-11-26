#!/usr/bin/env python3
"""Build a local, checkout-specific symbol map without importing application code.

This is navigation metadata, not a semantic call graph. It reads tracked source
only, emits symbol names and line numbers (not source bodies or config values),
and never contacts providers or executes application code.
"""
import argparse
import ast
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = {".py"}
JS = {".js", ".jsx", ".mjs", ".ts", ".tsx"}
JS_DECL = re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:function|class|const|let)\s+([A-Za-z_$][\w$]*)")
SQL_DECL = re.compile(r"\bCREATE\s+(?:OR\s+REPLACE\s+)?(?:TABLE|VIEW|FUNCTION|INDEX|TYPE|SCHEMA)\s+(?:IF\s+NOT\s+EXISTS\s+)?([\w.]+)", re.I)

def python_symbols(source):
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            yield f"{type(node).__name__} {node.name}", node.lineno
            for deco in node.decorator_list:
                if (isinstance(deco, ast.Call) and isinstance(deco.func, ast.Attribute)
                        and deco.func.attr in {"get", "post", "put", "patch", "delete", "api_route", "websocket"}
                        and deco.args and isinstance(deco.args[0], ast.Constant)
                        and isinstance(deco.args[0].value, str) and deco.args[0].value.startswith("/")):
                    yield f"route {deco.func.attr.upper()} {deco.args[0].value}", deco.lineno
            if isinstance(node, ast.ClassDef):
                for method in node.body:
                    if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        yield f"method {node.name}.{method.name}", method.lineno
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.ImportFrom):
                yield "import " + "." * node.level + (node.module or ""), node.lineno
            else:
                for alias in node.names:
                    yield "import " + alias.name, node.lineno

def symbols(path, source):
    suffix = path.suffix
    if suffix in PY:
        yield from python_symbols(source)
    elif suffix in JS:
        # Lexical hints, not a JS parser; may include nested declarations.
        for num, line in enumerate(source.splitlines(), 1):
            match = JS_DECL.match(line)
            if match:
                yield "declaration " + match.group(1), num
    elif suffix == ".sql":
        for num, line in enumerate(source.splitlines(), 1):
            for match in SQL_DECL.finditer(line):
                yield "SQL object " + match.group(1), num

def render():
    paths = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT))
    lines = ["# Local codebase symbol index", "", f"HEAD: {sha}; tracked working tree modified: {dirty}", "",
             "Python: AST declarations/imports and literal route decorators. JS and SQL: lexical hints. No source bodies or configuration values.",
             "All tracked paths are listed, including files without supported symbol extraction.", ""]
    for name in sorted(filter(None, paths)):
        path = ROOT / name
        lines.append(f"## {name}")
        if path.is_symlink() or not path.is_file() or path.suffix not in PY | JS | {".sql"}:
            lines.extend(["", "Path only; no symbol extraction.", ""])
            continue
        try:
            source = path.read_text(encoding="utf-8")
            entries = list(symbols(path, source))
            if path.suffix in PY:
                module_doc = ast.get_docstring(ast.parse(source))
                if module_doc:
                    first_line = module_doc.splitlines()[0].strip()
                    lines.extend(["", "Module docstring (source-authored; may be stale): " + first_line])
        except (OSError, UnicodeError, SyntaxError) as exc:
            lines.extend(["", f"Extraction unavailable: {type(exc).__name__}", ""])
            continue
        lines.extend([""] + [f"- `{label}` (L{line})" for label, line in entries] + [""])
    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    # Never replace any tracked source or repository documentation by accident.
    if output.is_relative_to(ROOT):
        raise SystemExit("Choose an output outside the repository (for example /tmp/dragonzpyder-symbols.md).")
    output.write_text(render(), encoding="utf-8")

if __name__ == "__main__":
    main()
