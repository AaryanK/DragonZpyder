#!/usr/bin/env python3
"""Build a local, checkout-specific symbol map without importing application code.

This is navigation metadata, not a semantic call graph. It reads tracked source
only, emits symbol names and line numbers (not source bodies or config values),
and never contacts providers or executes application code.
"""
import argparse
import ast
import os
import posixpath
from urllib.parse import quote
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
            doc = ast.get_docstring(node)
            if doc:
                yield f"{node.name} — {doc.splitlines()[0]}", node.lineno
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = node.args
                names = [a.arg for a in args.posonlyargs + args.args + args.kwonlyargs]
                yield f"parameters {node.name}: " + ", ".join(names), node.lineno
                for call in ast.walk(node):
                    if isinstance(call, ast.Call):
                        if isinstance(call.func, ast.Name):
                            yield f"{node.name} call candidate: {call.func.id}", call.lineno
                        elif isinstance(call.func, ast.Attribute):
                            yield f"{node.name} call candidate: .{call.func.attr}", call.lineno
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
                        doc = ast.get_docstring(method)
                        if doc:
                            yield f"{node.name}.{method.name} — {doc.splitlines()[0]}", method.lineno
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

def tracked(root):
    return sorted(os.fsdecode(p) for p in subprocess.check_output(["git", "ls-files", "-z"], cwd=root).split(b"\0") if p)

def file_info(root, name):
    path = root / name
    summary, entries, imports = "", [], []
    if path.is_symlink() or not path.is_file():
        return "Unavailable file or symlink (not followed).", entries, imports
    if path.stat().st_size > 2_000_000:
        return "File exceeds static inspection size limit.", entries, imports
    try:
        source = path.read_text(encoding="utf-8")
        if "\0" in source:
            raise UnicodeError("binary")
        entries = list(symbols(path, source))
        if path.suffix in PY:
            tree = ast.parse(source)
            doc = ast.get_docstring(tree)
            summary = doc.splitlines()[0] if doc else "No module docstring; inspect declarations and curated inventory."
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(a.name for a in node.names)
                elif isinstance(node, ast.ImportFrom):
                    module = "." * node.level + (node.module or "")
                    imports.append(module)
                    imports.extend(module + ("" if module.endswith(".") else ".") + a.name for a in node.names)
        else:
            summary = "Source structure scanned; consult curated inventory for semantic purpose."
            for n, line in enumerate(source.splitlines(), 1):
                if path.suffix in JS:
                    imports.extend(re.findall(r"""(?:\bfrom\s*|\bimport\s*\(|\brequire\s*\(|^\s*import\s*)['"]([^'"]+)['"]""", line))
                elif path.suffix in {".java", ".kt", ".kts"}:
                    # Lexical JVM navigation only; no compiler/type resolution.
                    match = re.match(r"^\s*(?:@\w+\s+)*(?:(?:public|private|protected|internal|static|final|abstract|open|override|suspend|data|sealed|inline|enum)\s+)*(class|interface|object|fun|enum)\s+([A-Za-z_$][\w$]*)", line)
                    if match:
                        entries.append((match.group(1) + " " + match.group(2), n))
                    elif path.suffix == ".java":
                        method = re.match(r"^\s*(?:(?:public|private|protected|static|final|synchronized|abstract|native)\s+)*(?:[\w.$<>\[\],?]+\s+)+([A-Za-z_$][\w$]*)\s*\(", line)
                        if method and method.group(1) not in {"if", "for", "while", "switch", "return", "throw", "catch"}:
                            entries.append(("method candidate " + method.group(1), n))
                    imp = re.match(r"^\s*import\s+(?:static\s+)?([\w.$]+(?:\.\*)?)", line)
                    if imp:
                        imports.append(imp.group(1))
                    pkg = re.match(r"^\s*package\s+([\w.]+)", line)
                    if pkg:
                        entries.append(("package " + pkg.group(1), n))
                elif path.suffix == ".xml":
                    for match in re.finditer(r"<([A-Za-z_][\w.:-]*)\b", line):
                        entries.append(("XML element " + match.group(1), n))
                    match = re.search(r'\b(?:android:name|name)\s*=\s*["\x27]([\w.$:-]+)["\x27]', line)
                    if match:
                        entries.append(("XML named element " + match.group(1), n))
                elif path.suffix == ".gradle" or path.name == "gradle.properties":
                    match = re.match(r"^\s*([A-Za-z_][\w.-]*)\s*(?:[={]|['\x27]|\d)", line)
                    if match:
                        entries.append(("Gradle key " + match.group(1), n))
                elif path.suffix == ".md" and re.match(r"^#{1,6} ", line):
                    entries.append(("heading " + line.lstrip("# ").strip()[:140], n))
                elif path.suffix in {".yaml", ".yml", ".toml", ".json"}:
                    match = re.match(r'^\s*"?([A-Za-z_][\w.-]*)"?\s*[:=]', line)
                    if match:
                        entries.append(("key " + match.group(1), n))
                elif path.suffix == ".css":
                    match = re.match(r"^\s*([.#][\w-]+)\s*[{,:]", line)
                    if match:
                        entries.append(("selector " + match.group(1), n))
                elif path.suffix == ".html":
                    imports.extend(re.findall(r"""(?:src|href)\s*=\s*['"]([^'"]+)['"]""", line))
                elif path.name.startswith("Dockerfile"):
                    match = re.match(r"^\s*(FROM|COPY|RUN|USER|CMD|ENTRYPOINT|EXPOSE|WORKDIR)\b", line)
                    if match:
                        entries.append(("Docker instruction " + match.group(1), n))
                elif path.name == ".env.example":
                    match = re.match(r"^\s*([A-Z_][A-Z0-9_]*)=", line)
                    if match:
                        entries.append(("configuration key " + match.group(1), n))
        return summary, entries, imports
    except (OSError, UnicodeError, SyntaxError) as exc:
        return "Extraction unavailable: " + type(exc).__name__, [], []

def module_names(name):
    p = Path(name)
    if p.suffix != ".py":
        return []
    parts = list(p.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    names = [".".join(parts)]
    if parts and parts[0] in {"api", "src", "web"}:
        names.append(".".join(parts[1:]))
    return [n for n in names if n]

def graph(paths, info):
    modules = {}
    available = set(paths)
    for p in paths:
        for m in module_names(p):
            modules.setdefault(m, set()).add(p)
    forward = {p: set() for p in paths}
    for p in paths:
        package = list(Path(p).parent.parts)
        for name in info[p][2]:
            if p.endswith(".py"):
                if name.startswith("."):
                    depth = len(name) - len(name.lstrip("."))
                    if depth > len(package):
                        continue
                    name = ".".join(package[:len(package)-depth+1] + ([name[depth:]] if name[depth:] else []))
                forward[p].update(modules.get(name, set()))
            elif name.startswith("."):
                candidate = posixpath.normpath(posixpath.join(posixpath.dirname(p), name))
                for n in [candidate] + [candidate + ext for ext in sorted(JS)]:
                    if n in available:
                        forward[p].add(n)
        forward[p].discard(p)
    reverse = {p: set() for p in paths}
    for p, dependencies in forward.items():
        for d in dependencies:
            reverse[d].add(p)
    return forward, reverse

def is_test(name):
    p = Path(name).name
    return p.startswith("test_") or ".test." in p or ".spec." in p or (p.endswith(("Test.java", "Test.kt", "Tests.java", "Tests.kt")))

def tests_for(name, paths, reverse):
    stem = re.sub(r"[^a-z0-9]+", "_", Path(name).stem.lower())
    result = {p for p in reverse[name] if is_test(p)}
    if len(stem) >= 5 and stem not in {"index", "router", "main"}:
        for p in paths:
            if is_test(p):
                test = re.sub(r"[^a-z0-9]+", "_", Path(p).stem.lower())
                if "_" + stem + "_" in "_" + test + "_" or (p.endswith((".java", ".kt")) and test in {stem + "test", stem + "tests"}):
                    result.add(p)
    return result

def clean(s):
    return str(s).replace("\n", " ").replace("\r", " ").replace(chr(96), "'")[:250]

def link(target, current):
    return quote(posixpath.relpath(target, posixpath.dirname(current) or "."), safe="/._-")

def file_page(name):
    return "files/" + name + ".md"

def folder_page(name):
    return "folders/" + ("" if name == "." else name + "/") + "INDEX.md"

def curated_notes(root):
    """Read maintained purpose rows, without treating them as live evidence."""
    path = root / "docs/codebase/FILE_INDEX.md"
    if not path.is_file():
        return {}
    result = {}
    pattern = re.compile(r"^\| \[\x60[^\x60]+\x60\]\(\.\./\.\./([^)]+)\) \| (.*) \| (Reviewed|Indexed) \|$")
    for line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match:
            result[match.group(1)] = (match.group(2), match.group(3))
    return result

def render(root=ROOT):
    paths = tracked(root)
    info = {p: file_info(root, p) for p in paths}
    curated = curated_notes(root)
    forward, reverse = graph(paths, info)
    dirs = {str(parent) for p in paths for parent in Path(p).parents}
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=root))
    caveat = "Static navigation only: summaries may be stale; references and tests are candidates, not a complete call graph or behavioral proof."
    pages = {}
    flat = ["# Local source index", "", f"HEAD: {sha}; tracked changes: {dirty}", "", caveat, ""]
    def links(items, current):
        return [f"- [{p}]({link(file_page(p), current)})" for p in sorted(items)] or ["- None found by static extraction."]
    for p in paths:
        current = file_page(p)
        summary, entries, imports = info[p]
        body = [f"# {p}", "", f"[Parent directory]({link(folder_page(str(Path(p).parent)), current)})", "",
                "Source summary: " + clean(summary), "", "## Symbols / structure", ""]
        declarations = [f"- L{n}: {clean(label)}" for label, n in sorted(set(entries), key=lambda e: (e[1], e[0]))]
        if p in curated:
            purpose, status = curated[p]
            body[6:6] = ["Maintained purpose (" + status + "): " + clean(purpose), ""]
        body += declarations or ["- No symbols extracted."]
        body += ["", "## Import/reference names", ""] + [f"- {clean(m)}" for m in sorted(set(imports)) if not re.match(r"^(https?://|data:)", m)]
        body += ["", "## Candidate dependencies", ""] + links(forward[p], current)
        body += ["", "## Candidate reverse dependencies", ""] + links(reverse[p], current)
        body += ["", "## Candidate related tests", ""] + links(tests_for(p, paths, reverse), current)
        pages[current] = "\n".join(body + ["", caveat, ""])
        flat += [f"## {p}", "", clean(summary), ""] + (["Maintained purpose (" + curated[p][1] + "): " + clean(curated[p][0]), ""] if p in curated else []) + declarations + [""]
    for d in sorted(dirs):
        current = folder_page(d)
        children = [q for q in dirs if q != d and str(Path(q).parent) == d]
        files = [p for p in paths if str(Path(p).parent) == d]
        pages[current] = "\n".join([f"# Directory: {d}", "", caveat, "", "## Child directories", ""] +
            [f"- [{q}]({link(folder_page(q), current)})" for q in sorted(children)] +
            ["", "## Files", ""] + links(files, current) + [""])
    pages["INDEX.md"] = "\n".join(["# Source navigation", "", f"HEAD: {sha}; tracked changes: {dirty}",
        f"Tracked files: {len(paths)}; directories: {len(dirs)}.", "", caveat, "",
        "[Browse folders](folders/INDEX.md) | [Flat index](SYMBOLS.md)", "", "## All directories", ""] +
        [f"- [{d}]({folder_page(d)})" for d in sorted(dirs)] + [""])
    pages["SYMBOLS.md"] = "\n".join(flat)
    return pages

def write_bundle(root, target):
    pages = render(root)
    for name, content in pages.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink() or not path.resolve().is_relative_to(target.resolve()):
            raise ValueError("Unsafe output path")
        path.write_text(content, encoding="utf-8")
    return len(pages)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    options = parser.add_mutually_exclusive_group(required=True)
    options.add_argument("--output", type=Path)
    options.add_argument("--directory", type=Path)
    args = parser.parse_args()
    target = (args.output or args.directory).resolve()
    if target.is_relative_to(ROOT):
        parser.error("Choose an output outside the repository.")
    if args.directory:
        if target.exists() and (not target.is_dir() or any(target.iterdir())):
            parser.error("Choose a new or empty directory to avoid stale pages.")
        print(f"Generated {write_bundle(ROOT, target)} navigation pages")
    else:
        target.write_text(render(ROOT)["SYMBOLS.md"], encoding="utf-8")

if __name__ == "__main__":
    main()
