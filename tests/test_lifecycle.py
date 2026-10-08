"""SF-06 isolated filesystem failure/collision/ownership qualification fixtures."""
from __future__ import annotations
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sf.cli import main
from sf.integration import IntegrationError
from sf.lifecycle import JOURNAL, execute_plan, plan_lifecycle, recover


def _profile(root: Path, *, version: str = "a") -> Path:
    path = root / f"profile-{version}.json"
    path.write_text(json.dumps({
        "schemaVersion": 1, "project": {"id": "sample"},
        "commands": {"check": {"argv": ["make", f"test-{version}"], "cwd": "."}},
        "components": [{"id": "svc", "path": ".", "stack": "custom", "checks": ["check"]}],
    }))
    return path


def _save_plan(root: Path, mode: str, profile: Path | None = None,
               ack: bool = False) -> Path:
    plan = plan_lifecycle(mode, root, profile, ack_manual=ack)
    p = root / "plan.json"
    p.write_text(json.dumps(plan, sort_keys=True))
    return p


class LifecycleTests(unittest.TestCase):
    def test_integrate_noop_and_owned_files_only(self):
        with tempfile.TemporaryDirectory() as d:
            r = Path(d)
            p = _profile(r)
            (r / "important.txt").write_bytes(b"do-not-touch\r\n")
            plan = _save_plan(r, "integrate", p)
            res = execute_plan(r, p, plan, mode="integrate")
            self.assertEqual(res["status"], "completed")
            self.assertEqual((r / "important.txt").read_bytes(), b"do-not-touch\r\n")
            self.assertTrue((r / ".s-f/OWNERSHIP.json").exists())
            self.assertTrue((r / "AGENTS.md").exists())
            self.assertFalse((r / JOURNAL).exists())
            newplan = _save_plan(r, "integrate", p)
            with patch("sf.lifecycle._make_journal", side_effect=AssertionError("unnecessary write")):
                self.assertEqual(execute_plan(r, p, newplan, mode="integrate")["status"], "no-op")

    def test_stale_or_forged_plan_fails_without_writing(self):
        with tempfile.TemporaryDirectory() as d:
            r = Path(d)
            p = _profile(r)
            plan = _save_plan(r, "integrate", p)
            candidate = json.loads(plan.read_text())
            candidate["changes"][0]["after"]["content"] = "injected"
            plan.write_text(json.dumps(candidate))
            with self.assertRaises(IntegrationError):
                execute_plan(r, p, plan, mode="integrate")
            self.assertFalse((r / ".s-f").exists())
            self.assertFalse((r / JOURNAL).exists())
            plan = _save_plan(r, "integrate", p)
            (r / "AGENTS.md").write_text("project-owned rules")
            with self.assertRaises(IntegrationError):
                execute_plan(r, p, plan, mode="integrate")
            self.assertFalse((r / ".s-f").exists())

    def test_manual_route_ack_preserves_existing_instructions_and_ci(self):
        with tempfile.TemporaryDirectory() as d:
            r = Path(d)
            p = _profile(r)
            (r / "AGENTS.md").write_bytes(b"local-only\r\n")
            (r / "CLAUDE.md").write_bytes(b"claude\r\n")
            (r / ".github/workflows").mkdir(parents=True)
            (r / ".github/workflows/run.yml").write_bytes(b"custom\r\n")
            with self.assertRaises(IntegrationError):
                execute_plan(r, p, _save_plan(r, "integrate", p), mode="integrate")
            plan = _save_plan(r, "integrate", p, ack=True)
            result = execute_plan(r, p, plan, mode="integrate", ack_manual=True)
            self.assertEqual(result["status"], "completed")
            self.assertEqual((r / "AGENTS.md").read_bytes(), b"local-only\r\n")
            self.assertEqual((r / "CLAUDE.md").read_bytes(), b"claude\r\n")
            self.assertEqual((r / ".github/workflows/run.yml").read_bytes(), b"custom\r\n")
            self.assertFalse(any(x["path"] == "AGENTS.md" for x in json.loads(
                (r / ".s-f/OWNERSHIP.json").read_text())["files"]))

    def test_interrupt_after_first_effect_recover_idempotently(self):
        with tempfile.TemporaryDirectory() as d:
            r = Path(d)
            p = _profile(r)
            plan = _save_plan(r, "integrate", p)
            from sf import lifecycle
            original = lifecycle._checked_effect
            calls = []
            def fail(root, step):
                if calls:
                    raise OSError("simulated crash")
                calls.append(step["path"])
                return original(root, step)
            with patch("sf.lifecycle._checked_effect", side_effect=fail):
                with self.assertRaises(OSError):
                    execute_plan(r, p, plan, mode="integrate")
            self.assertTrue((r / JOURNAL).exists())
            with self.assertRaises(IntegrationError):
                plan_lifecycle("integrate", r, p)
            self.assertEqual(recover(r)["status"], "completed")
            self.assertEqual(recover(r)["status"], "no-op")
            self.assertFalse((r / JOURNAL).exists())
            self.assertTrue((r / ".s-f/OWNERSHIP.json").exists())

    def test_interrupted_target_modified_recovery_quarantines(self):
        with tempfile.TemporaryDirectory() as d:
            r = Path(d)
            p = _profile(r)
            plan = _save_plan(r, "integrate", p)
            from sf import lifecycle
            original = lifecycle._checked_effect
            calls = []
            def fail(root, step):
                if calls:
                    raise RuntimeError("kill")
                calls.append(step["path"])
                return original(root, step)
            with patch("sf.lifecycle._checked_effect", side_effect=fail):
                with self.assertRaises(RuntimeError):
                    execute_plan(r, p, plan, mode="integrate")
            (r / calls[0]).write_text("unexpected edit")
            with self.assertRaises(IntegrationError):
                recover(r)
            self.assertTrue((r / JOURNAL).exists())
            self.assertFalse((r / ".s-f/OWNERSHIP.json").exists())

    def test_upgrade_clean_and_repeated_noop(self):
        with tempfile.TemporaryDirectory() as d:
            r = Path(d)
            old = _profile(r, version="a")
            execute_plan(r, old, _save_plan(r, "integrate", old), mode="integrate")
            new = _profile(r, version="b")
            plan = _save_plan(r, "upgrade", new)
            self.assertEqual(execute_plan(r, new, plan, mode="upgrade")["status"], "completed")
            self.assertIn("test-b", (r / ".s-f/profile.json").read_text())
            self.assertEqual(execute_plan(r, new, _save_plan(r, "upgrade", new),
                                          mode="upgrade")["status"], "no-op")

    def test_upgrade_preserves_locally_modified_owned_file(self):
        with tempfile.TemporaryDirectory() as d:
            r = Path(d)
            old = _profile(r)
            execute_plan(r, old, _save_plan(r, "integrate", old), mode="integrate")
            (r / ".s-f/INSTRUCTIONS.md").write_text("owner changed this")
            new = _profile(r, version="b")
            plan = _save_plan(r, "upgrade", new)
            with self.assertRaises(IntegrationError):
                execute_plan(r, new, plan, mode="upgrade")
            self.assertEqual((r / ".s-f/INSTRUCTIONS.md").read_text(), "owner changed this")
            self.assertIn("test-a", (r / ".s-f/profile.json").read_text())
            self.assertFalse((r / JOURNAL).exists())

    def test_remove_only_verified_owned_contents_preserves_extra_files(self):
        with tempfile.TemporaryDirectory() as d:
            r = Path(d)
            old = _profile(r)
            execute_plan(r, old, _save_plan(r, "integrate", old), mode="integrate")
            (r / ".s-f/external.txt").write_bytes(b"keep me")
            (r / "regular-source.py").write_bytes(b"print('preserve')\n")
            result = execute_plan(r, None, _save_plan(r, "remove"), mode="remove")
            self.assertEqual(result["status"], "completed")
            self.assertFalse((r / "AGENTS.md").exists())
            self.assertFalse((r / ".s-f/OWNERSHIP.json").exists())
            self.assertEqual((r / ".s-f/external.txt").read_bytes(), b"keep me")
            self.assertEqual((r / "regular-source.py").read_bytes(), b"print('preserve')\n")

    def test_remove_modified_owned_blocks_entire_operation(self):
        with tempfile.TemporaryDirectory() as d:
            r = Path(d)
            old = _profile(r)
            execute_plan(r, old, _save_plan(r, "integrate", old), mode="integrate")
            (r / "AGENTS.md").write_text("edited owner instructions")
            with self.assertRaises(IntegrationError):
                execute_plan(r, None, _save_plan(r, "remove"), mode="remove")
            self.assertTrue((r / ".s-f/OWNERSHIP.json").exists())
            self.assertFalse((r / JOURNAL).exists())

    def test_remove_crash_recover(self):
        with tempfile.TemporaryDirectory() as d:
            r = Path(d)
            old = _profile(r)
            execute_plan(r, old, _save_plan(r, "integrate", old), mode="integrate")
            plan = _save_plan(r, "remove")
            from sf import lifecycle
            original = lifecycle._checked_effect
            calls = []
            def fail(root, step):
                if calls:
                    raise OSError("crash")
                calls.append(step["path"])
                return original(root, step)
            with patch("sf.lifecycle._checked_effect", side_effect=fail):
                with self.assertRaises(OSError):
                    execute_plan(r, None, plan, mode="remove")
            self.assertTrue((r / JOURNAL).exists())
            self.assertEqual(recover(r)["status"], "completed")
            self.assertFalse((r / ".s-f").exists())
            self.assertFalse((r / JOURNAL).exists())

    def test_forged_journal_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            r = Path(d)
            p = _profile(r)
            plan = _save_plan(r, "integrate", p)
            with patch("sf.lifecycle._checked_effect", side_effect=OSError("stopped")):
                with self.assertRaises(OSError):
                    execute_plan(r, p, plan, mode="integrate")
            path = r / JOURNAL
            data = json.loads(path.read_text())
            data["steps"][0]["path"] = "secret.txt"
            path.write_text(json.dumps(data))
            with self.assertRaises(IntegrationError):
                recover(r)
            self.assertFalse((r / "secret.txt").exists())

    def test_bad_symlink_blocks_install(self):
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as ext:
            r = Path(d)
            p = _profile(r)
            try:
                (r / ".s-f").symlink_to(ext, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symlink unavailable")
            with self.assertRaises(IntegrationError):
                execute_plan(r, p, _save_plan(r, "integrate", p), mode="integrate")
            self.assertFalse((Path(ext) / "profile.json").exists())

    def test_plan_is_read_only(self):
        with tempfile.TemporaryDirectory() as d:
            r = Path(d)
            p = _profile(r)
            before = sorted(x.relative_to(r).as_posix() for x in r.rglob("*"))
            plan_lifecycle("integrate", r, p)
            self.assertEqual(before, sorted(x.relative_to(r).as_posix() for x in r.rglob("*")))
            self.assertFalse((r / JOURNAL).exists())

    def test_repeat_remove_without_owned_namespace_is_noop(self):
        with tempfile.TemporaryDirectory() as d:
            r = Path(d)
            old = _profile(r)
            execute_plan(r, old, _save_plan(r, "integrate", old), mode="integrate")
            execute_plan(r, None, _save_plan(r, "remove"), mode="remove")
            repeated = _save_plan(r, "remove")
            self.assertEqual(execute_plan(r, None, repeated, mode="remove")["status"], "no-op")
            self.assertFalse((r / JOURNAL).exists())

    def test_cli_dry_run_apply_upgrade_remove_recover(self):
        with tempfile.TemporaryDirectory() as d:
            r = Path(d)
            old = _profile(r)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(["integrate", "--dry-run", "--root", str(r),
                                       "--profile", str(old)]), 0)
            plan = r / "plan.json"
            plan.write_text(output.getvalue())
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["integrate", "--apply", str(plan), "--root", str(r),
                                       "--profile", str(old)]), 0)
            new = _profile(r, version="b")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(["upgrade", "--dry-run", "--root", str(r),
                                       "--profile", str(new)]), 0)
            plan.write_text(output.getvalue())
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["upgrade", "--apply", str(plan), "--root", str(r),
                                       "--profile", str(new)]), 0)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(["remove", "--dry-run", "--root", str(r)]), 0)
            plan.write_text(output.getvalue())
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["remove", "--apply", str(plan), "--root", str(r)]), 0)
                self.assertEqual(main(["recover", "--root", str(r)]), 0)
            self.assertFalse((r / ".s-f").exists())

    def test_upgrade_crash_recovers_exact_new_profile(self):
        with tempfile.TemporaryDirectory() as d:
            r = Path(d)
            old = _profile(r)
            execute_plan(r, old, _save_plan(r, "integrate", old), mode="integrate")
            new = _profile(r, version="b")
            saved = _save_plan(r, "upgrade", new)
            from sf import lifecycle
            original = lifecycle._checked_effect
            calls = []
            def fail(root, step):
                if calls:
                    raise OSError("simulated interrupted upgrade")
                calls.append(step["path"])
                return original(root, step)
            with patch("sf.lifecycle._checked_effect", side_effect=fail):
                with self.assertRaises(OSError):
                    execute_plan(r, new, saved, mode="upgrade")
            self.assertTrue((r / JOURNAL).is_file())
            self.assertEqual(recover(r)["status"], "completed")
            self.assertIn("test-b", (r / ".s-f/profile.json").read_text())
            self.assertFalse((r / JOURNAL).exists())

    def test_journal_write_failure_prevents_target_effect(self):
        with tempfile.TemporaryDirectory() as d:
            r = Path(d)
            p = _profile(r)
            saved = _save_plan(r, "integrate", p)
            with patch("sf.lifecycle._make_journal", side_effect=OSError("disk error")):
                with self.assertRaises(OSError):
                    execute_plan(r, p, saved, mode="integrate")
            self.assertFalse((r / ".s-f").exists())
            self.assertFalse((r / "AGENTS.md").exists())

    def test_plan_invalid_after_profile_changes(self):
        with tempfile.TemporaryDirectory() as d:
            r = Path(d)
            p = _profile(r)
            saved = _save_plan(r, "integrate", p)
            data = json.loads(p.read_text())
            data["commands"]["check"]["argv"] = ["different", "check"]
            p.write_text(json.dumps(data))
            with self.assertRaises(IntegrationError):
                execute_plan(r, p, saved, mode="integrate")
            self.assertFalse((r / JOURNAL).exists())
