import json
import tempfile
import unittest
from pathlib import Path
from sf.cli import main
from sf.profile import (
    ProfileError, read_profile, validate_profile, validate_project_paths,
    MAX_PROFILE_BYTES, component_order,
)

GOOD = {
    "schemaVersion": 1,
    "project": {"id": "example"},
    "commands": {"test": {"argv": ["python", "-m", "unittest"], "cwd": "src"}},
}


class ProfileTests(unittest.TestCase):
    def test_valid_bootstrap_compatibility(self):
        self.assertEqual(validate_profile(GOOD), GOOD)
        self.assertEqual(main(["doctor"]), 0)

    def test_unknown_schema_and_extras(self):
        for data in ({**GOOD, "schemaVersion": 2}, {**GOOD, "unexpected": True}):
            with self.assertRaises(ProfileError):
                validate_profile(data)

    def test_path_escape(self):
        for path in ("../outside", "/absolute", "C:/outside", "a//b", "a/./b",
                     "a/../b", "a\\b", "\x00"):
            bad = {**GOOD, "commands": {"test": {"argv": ["echo"], "cwd": path}}}
            with self.subTest(path=path), self.assertRaises(ProfileError):
                validate_profile(bad)

    def test_safe_explicit_root(self):
        profile = {**GOOD, "commands": {"test": {"argv": ["echo"], "cwd": "."}}}
        self.assertEqual(validate_profile(profile), profile)

    def test_malformed_command_options(self):
        for extra in (
            {"network": "yes"}, {"risk": ["build"]}, {"risk": "shell"},
            {"timeoutSeconds": 0}, {"timeoutSeconds": True},
            {"argv": ["echo", "\x00bad"]}, {"cwd": 0}, {"unknown": 1},
        ):
            spec = {"argv": ["echo"], "cwd": ".", **extra}
            with self.subTest(extra=extra), self.assertRaises(ProfileError):
                validate_profile({**GOOD, "commands": {"test": spec}})

    def test_oversized(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "profile.json"
            path.write_bytes(b" " * (MAX_PROFILE_BYTES + 1))
            with self.assertRaises(ProfileError):
                read_profile(path)

    def test_duplicate_json_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "profile.json"
            path.write_text('{"schemaVersion":1,"schemaVersion":1}', encoding="utf-8")
            with self.assertRaises(ProfileError):
                read_profile(path)

    def test_validation_cli_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "profile.json"
            path.write_text(json.dumps(GOOD), encoding="utf-8")
            self.assertEqual(main(["profile", "validate", str(path)]), 0)
            path.write_text('{"schemaVersion": 1}', encoding="utf-8")
            self.assertEqual(main(["profile", "validate", str(path)]), 2)

    def test_rooted_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            validate_project_paths(GOOD, root)
            (root / "src").rmdir()
            with self.assertRaises(ProfileError):
                validate_project_paths(GOOD, root)
            (root / "src").write_text("file")
            with self.assertRaises(ProfileError):
                validate_project_paths(GOOD, root)

    def test_root_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            link = root / "linked"
            try:
                link.symlink_to(root / "src", target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable on this runner")
            profile = {**GOOD, "commands": {"test": {"argv": ["echo"], "cwd": "linked"}}}
            with self.assertRaises(ProfileError):
                validate_project_paths(profile, root)

    def test_components_dependency_graph(self):
        profile = {**GOOD, "components": [
            {"id": "app", "path": "src", "stack": "python", "dependsOn": ["core"], "checks": ["test"]},
            {"id": "core", "path": ".", "stack": "custom"},
        ]}
        self.assertEqual(component_order(validate_profile(profile)), ["core", "app"])

    def test_missing_or_cyclic_dependency(self):
        for components in (
            [{"id": "a", "path": ".", "stack": "custom", "dependsOn": ["missing"]}],
            [{"id": "a", "path": ".", "stack": "custom", "dependsOn": ["a"]}],
            [
                {"id": "a", "path": ".", "stack": "custom", "dependsOn": ["b"]},
                {"id": "b", "path": ".", "stack": "custom", "dependsOn": ["a"]},
            ],
        ):
            with self.subTest(components=components), self.assertRaises(ProfileError):
                validate_profile({**GOOD, "components": components})

    def test_duplicate_component_names_and_bad_checks(self):
        for components in (
            [{"id": "UI", "path": ".", "stack": "node"},
             {"id": "ui", "path": ".", "stack": "node"}],
            [{"id": "a", "path": ".", "stack": "custom", "checks": ["unknown"]}],
            [{"id": "a", "path": ".", "stack": "custom", "dependsOn": ["a", "a"]}],
        ):
            with self.subTest(components=components), self.assertRaises(ProfileError):
                validate_profile({**GOOD, "components": components})
