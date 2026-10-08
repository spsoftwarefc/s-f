import json
import tempfile
import unittest
from pathlib import Path

from sf.inventory import inventory, InventoryError
from sf.cli import main


class InventoryTests(unittest.TestCase):
    def test_mixed_repository_and_nested_instructions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src" / "nested").mkdir(parents=True)
            (root / ".github" / "workflows").mkdir(parents=True)
            for p in ("pyproject.toml", "src/package.json", "src/nested/AGENTS.md", ".github/workflows/build.yml"):
                file = root / p
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text("not executable", encoding="utf-8")
            before = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            result = inventory(root)
            after = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            self.assertEqual(before, after)
            self.assertEqual([c["stackHint"] for c in result["components"]], ["python", "node"])
            self.assertEqual(result["instructionFiles"], ["src/nested/AGENTS.md"])
            self.assertEqual(result["workflowFiles"], [".github/workflows/build.yml"])
            self.assertEqual(result["commandsExecuted"], [])
            self.assertFalse(result["releaseReady"])

    def test_unknown_stack(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "custom.build").write_text("ignored", encoding="utf-8")
            self.assertEqual(inventory(Path(tmp))["components"], [])

    def test_symlink_not_followed(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as other:
            root = Path(tmp)
            (Path(other) / "Cargo.toml").write_text("secret", encoding="utf-8")
            try:
                (root / "external").symlink_to(Path(other), target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable")
            self.assertEqual(inventory(root)["components"], [])

    def test_missing_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(InventoryError):
                inventory(Path(tmp) / "absent")

    def test_cli_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(main(["inventory", tmp]), 0)
