import importlib
import pathlib
import sys
import unittest


class PackageBoundaryTests(unittest.TestCase):
    def test_modern_package_imports_without_legacy_program(self):
        importlib.import_module("dragonzpyder")
        self.assertNotIn("DragonZpyder", sys.modules)

    def test_legacy_program_is_not_present_at_repository_root(self):
        root = pathlib.Path(__file__).resolve().parents[1]
        self.assertFalse((root / "DragonZpyder").exists())


if __name__ == "__main__":
    unittest.main()
