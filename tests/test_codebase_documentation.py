"""Offline navigation and maintenance checks."""
import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

index = load("build_codebase_index")
gate = load("check_codebase_docs")

class DocumentationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "repo"
        self.root.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.write("api/demo.py", '"""Demo entrypoint."""\nfrom .helper import work\n@router.get("/demo")\ndef handler():\n    return work()\n')
        self.write("api/helper.py", "def work():\n    return 1\n")
        self.write("api/tests/test_helper.py", "from api.helper import work\n")
        self.write("web/main.js", 'import { x } from "./helper.js";\nexport function run() {}\n')
        self.write("web/helper.js", "export const x = 1;\n")
        self.write("README.md", "# Fixture\n")
        self.git("add", ".")
        self.git("commit", "-qm", "base")
        self.base = self.git("rev-parse", "HEAD").strip()

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, text=True)

    def write(self, name, content):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    def commit(self):
        self.git("add", "-A")
        self.git("commit", "-qm", "change")

    def test_index_pages_and_links(self):
        pages = index.render(self.root)
        self.assertIn("route GET /demo", pages["files/api/demo.py.md"])
        self.assertIn("helper.py", pages["files/api/demo.py.md"])
        self.assertIn("demo.py", pages["files/api/helper.py.md"])
        self.assertIn("test_helper.py", pages["files/api/helper.py.md"])
        self.assertIn("helper.js", pages["files/web/main.js.md"])
        self.assertIn("folders/api/tests/INDEX.md", pages)
        self.assertIn("files/README.md.md", pages)
        target = Path(self.tmp.name) / "output"
        self.assertEqual(index.write_bundle(self.root, target), len(pages))
        self.assertTrue((target / "INDEX.md").is_file())

    def test_changed_file_needs_new_record(self):
        self.write("api/helper.py", "def work():\n    return 2\n")
        self.commit()
        self.assertEqual(gate.missing_records(self.root, self.base), ["api/helper.py"])
        self.write(gate.LEDGER, "- \x60api/helper.py\x60: Change fixture return value; tests cover behavior.\n")
        self.commit()
        self.assertEqual(gate.missing_records(self.root, self.base), [])

    def test_rename_requires_both_paths(self):
        (self.root / "api/helper.py").rename(self.root / "api/new.py")
        self.commit()
        self.assertEqual(gate.missing_records(self.root, self.base), ["api/helper.py", "api/new.py"])

    def test_documentation_only(self):
        self.write("README.md", "# Updated fixture\n")
        self.commit()
        self.assertEqual(gate.missing_records(self.root, self.base), [])

if __name__ == "__main__":
    unittest.main()
