import json
import tempfile
import unittest
from pathlib import Path

from sf.adapters import adapter_hints, declared_check_plan
from sf.cli import main
from sf.profile import ProfileError

PROFILE = {
    "schemaVersion": 1,
    "project": {"id": "sample"},
    "commands": {
        "check-core": {"argv": ["cargo", "test", "--locked"], "cwd": "core", "timeoutSeconds": 200},
        "check-ui": {"argv": ["npm", "test", "--", "--run"], "cwd": "ui", "network": False},
        "check-custom": {"argv": ["make", "verify"], "cwd": "."},
    },
    "components": [
        {"id": "ui", "path": "ui", "stack": "node",
         "dependsOn": ["core"], "checks": ["check-ui"]},
        {"id": "core", "path": "core", "stack": "rust", "checks": ["check-core"]},
        {"id": "unknown", "path": ".", "stack": "custom", "checks": ["check-custom"]},
    ],
}


class AdaptersTests(unittest.TestCase):
    def test_deterministic_declared_plan(self):
        actual = declared_check_plan(PROFILE)
        self.assertEqual([x["id"] for x in actual["orderedComponents"]],
                         ["core", "ui", "unknown"])
        self.assertEqual(actual["orderedComponents"][0]["checks"][0]["argv"],
                         ["cargo", "test", "--locked"])
        self.assertEqual(actual["commandsExecuted"], [])
        self.assertFalse(actual["executionAuthorized"])
        self.assertFalse(actual["releaseQualified"])
        self.assertEqual(actual, declared_check_plan(PROFILE))

    def test_adapter_hints_are_non_authoritative(self):
        for stack in ("python", "node", "rust", "go", "custom"):
            with self.subTest(stack=stack):
                for hint in adapter_hints(stack):
                    self.assertFalse(hint["authoritative"])
                    self.assertFalse(hint["executed"])
                    self.assertIsInstance(hint["argv"], list)
        self.assertEqual(adapter_hints("custom"), [])
        with self.assertRaises(ProfileError):
            adapter_hints("swift")

    def test_cli_rooted_plan_and_missing_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "core").mkdir()
            (root / "ui").mkdir()
            profile = root / "profile.json"
            profile.write_text(json.dumps(PROFILE), encoding="utf-8")
            self.assertEqual(main(["profile", "plan", str(profile), "--root", str(root)]), 0)
            (root / "ui").rmdir()
            self.assertEqual(main(["profile", "plan", str(profile), "--root", str(root)]), 2)

    def test_untrusted_command_is_not_executed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            marker = root / "danger"
            profile = {
                "schemaVersion": 1,
                "project": {"id": "safe"},
                "commands": {"bad": {
                    "argv": ["python", "-c", f"open({str(marker)!r}, 'w').write('bad')"],
                    "cwd": ".",
                }},
                "components": [{"id": "x", "path": ".", "stack": "custom", "checks": ["bad"]}],
            }
            declared_check_plan(profile)
            self.assertFalse(marker.exists())
