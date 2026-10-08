import json
import tempfile
import unittest
from pathlib import Path
from sf.cli import main
from sf.profile import ProfileError, read_profile, validate_profile, MAX_PROFILE_BYTES

GOOD = {"schemaVersion": 1, "project": {"id": "example"}, "commands": {"test": {"argv": ["python", "-m", "unittest"], "cwd": "src"}}}


class ProfileTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(validate_profile(GOOD), GOOD)
        self.assertEqual(main(["doctor"]), 0)

    def test_unknown_schema_and_extras(self):
        for data in ({**GOOD, "schemaVersion": 2}, {**GOOD, "unexpected": True}):
            with self.assertRaises(ProfileError):
                validate_profile(data)

    def test_path_escape(self):
        for path in ("../outside", "/absolute", "C:/outside", ".", "a//b"):
            bad = {**GOOD, "commands": {"test": {"argv": ["echo"], "cwd": path}}}
            with self.assertRaises(ProfileError):
                validate_profile(bad)

    def test_oversized(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "profile.json"
            path.write_bytes(b" " * (MAX_PROFILE_BYTES + 1))
            with self.assertRaises(ProfileError):
                read_profile(path)

    def test_validation_cli_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "profile.json"
            path.write_text(json.dumps(GOOD), encoding="utf-8")
            self.assertEqual(main(["profile", "validate", str(path)]), 0)
            path.write_text('{"schemaVersion": 1}', encoding="utf-8")
            self.assertEqual(main(["profile", "validate", str(path)]), 2)
