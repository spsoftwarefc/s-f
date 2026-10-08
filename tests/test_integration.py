"""SF-05 installation planning: no writes, no execution, no silent replacement."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sf.cli import main
from sf.integration import IntegrationError, plan_install
from sf.profile import ProfileError


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def filesystem(root: Path) -> dict:
    return {p.relative_to(root).as_posix():
            ("symlink", p.readlink().as_posix()) if p.is_symlink() else
            ("dir",) if p.is_dir() else ("file", sha(p))
            for p in root.rglob("*")}


def profile(root: Path) -> Path:
    file = root / "project-profile.json"
    file.write_text(json.dumps({
        "schemaVersion": 1, "project": {"id": "test"},
        "commands": {"check": {"argv": ["make", "verify"], "cwd": "."}},
        "components": [{"id": "one", "path": ".", "stack": "custom", "checks": ["check"]}],
    }), encoding="utf-8")
    return file


class IntegrationTests(unittest.TestCase):
    def test_dry_run_no_writes_and_stable_serialization(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = profile(root)
            before = filesystem(root)
            first = plan_install(root, p)
            second = plan_install(root, p)
            self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))
            self.assertEqual(filesystem(root), before)
            self.assertEqual(first["readiness"], "plan-only")
            self.assertEqual(first["conflicts"], [])
            self.assertFalse(first["installationAuthorized"])
            self.assertFalse(first["releaseQualified"])
            self.assertEqual(first["filesWritten"], [])
            self.assertEqual(first["baseline"]["dirtyState"], "unknown")
            self.assertEqual({x["disposition"] for x in first["changes"]}, {"add"})
            self.assertIn("AGENTS.md", {x["path"] for x in first["changes"]})
            for change in first["changes"]:
                self.assertEqual(change["expected"]["state"], "absent")
                self.assertEqual(hashlib.sha256(change["content"].encode()).hexdigest(),
                                 change["desiredSha256"])

    def test_existing_project_instructions_and_ci_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = profile(root)
            (root / ".github" / "workflows").mkdir(parents=True)
            (root / ".github" / "workflows" / "custom.yml").write_bytes(b"custom yaml\r\n")
            (root / "AGENTS.md").write_bytes(b"NO REPLACE\r\n")
            (root / "CLAUDE.md").write_bytes(b"STILL OWNED\n")
            (root / "package.json").write_bytes(b"{}\n")
            before = filesystem(root)
            plan = plan_install(root, p)
            self.assertEqual(filesystem(root), before)
            self.assertNotIn("AGENTS.md", [op["path"] for op in plan["changes"]])
            self.assertEqual(plan["ci"]["writesPlanned"], [])
            self.assertEqual(plan["ci"]["proposal"], "review-existing-ci")
            self.assertEqual(plan["ci"]["existingWorkflows"], [".github/workflows/custom.yml"])
            self.assertTrue(any(c["reason"] == "existing-instructions-manual-routing"
                                for c in plan["conflicts"]))
            self.assertEqual(plan["readiness"], "blocked")
            self.assertIn("CLAUDE.md", plan["preserved"]["instructionFiles"])

    def test_existing_owned_namespace_never_automatically_adopted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = profile(root)
            (root / ".s-f").mkdir()
            (root / ".s-f" / "notes.txt").write_text("project data")
            before = filesystem(root)
            out = plan_install(root, p)
            self.assertEqual(filesystem(root), before)
            self.assertEqual(len([c for c in out["conflicts"] if c["path"].startswith(".s-f/")]), 4)
            self.assertTrue(all(c["disposition"] == "blocked"
                                for c in out["changes"] if c["path"].startswith(".s-f/")))

    def test_symlinked_namespace_blocked(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as other:
            root = Path(tmp)
            p = profile(root)
            try:
                (root / ".s-f").symlink_to(other, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable")
            before = filesystem(root)
            out = plan_install(root, p)
            self.assertEqual(filesystem(root), before)
            self.assertTrue(all(c["reason"] == "symlink" for c in out["conflicts"]
                                if c["path"].startswith(".s-f/")))
            self.assertFalse(Path(other, "PROJECT.md").exists())

    def test_casefold_collision_blocks_route_and_owned_namespace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = profile(root)
            (root / "agents.md").write_text("case collision")
            (root / ".S-F").mkdir()
            out = plan_install(root, p)
            conflict_paths = {x["path"] for x in out["conflicts"]}
            self.assertIn("AGENTS.md", conflict_paths)
            self.assertIn(".s-f/profile.json", conflict_paths)
            self.assertEqual(out["readiness"], "blocked")
            self.assertFalse((root / ".s-f").exists())

    def test_file_instead_of_namespace_and_oversize_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = profile(root)
            (root / ".s-f").write_text("not a directory")
            (root / "AGENTS.md").write_bytes(b"Q" * (1024 * 1024 + 1))
            out = plan_install(root, p)
            reasons = {x["reason"] for x in out["conflicts"]}
            self.assertIn("non-directory-parent", reasons)
            self.assertIn("existing-instructions-manual-routing", reasons)

    def test_reject_missing_root_and_bad_profile_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = profile(root)
            with self.assertRaises(IntegrationError):
                plan_install(root / "missing", p)
            payload = json.loads(p.read_text())
            payload["commands"]["check"]["cwd"] = "missing"
            p.write_text(json.dumps(payload))
            with self.assertRaises(ProfileError):
                plan_install(root, p)

    def test_cli_conflict_and_success_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = profile(root)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(main(["integrate", "--dry-run", "--root", str(root),
                                       "--profile", str(p)]), 0)
            result = json.loads(out.getvalue())
            self.assertFalse(result["installationAuthorized"])
            (root / "AGENTS.md").write_text("existing")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["integrate", "--dry-run", "--root", str(root),
                                       "--profile", str(p)]), 1)
            with self.assertRaises(SystemExit) as err:
                main(["integrate", "--root", str(root), "--profile", str(p)])
            self.assertEqual(err.exception.code, 2)

    def test_no_untrusted_commands_executed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = profile(root)
            data = json.loads(p.read_text())
            data["commands"]["check"]["argv"] = ["touch", "BAD_COMMAND_EXECUTED"]
            p.write_text(json.dumps(data))
            with patch("subprocess.run", side_effect=AssertionError("invoked subprocess")):
                plan_install(root, p)
            self.assertFalse((root / "BAD_COMMAND_EXECUTED").exists())

    def test_known_owned_repeat_plan_is_noop_and_modified_owned_file_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = profile(root)
            initial = plan_install(root, p)
            # Simulate a correctly applied candidate only inside this throwaway fixture.
            for change in initial["changes"]:
                destination = root / change["path"]
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(change["content"], encoding="utf-8")
            repeated = plan_install(root, p)
            self.assertEqual(repeated["conflicts"], [])
            self.assertTrue(all(c["disposition"] == "unchanged" for c in repeated["changes"]))
            (root / ".s-f" / "PROJECT.md").write_text("locally edited")
            modified = plan_install(root, p)
            self.assertEqual(modified["readiness"], "blocked")
            self.assertIn(".s-f/PROJECT.md", [x["path"] for x in modified["conflicts"]])
