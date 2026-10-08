"""SF-07: repeatable portable integration qualification using throwaway target repos."""
from __future__ import annotations
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from sf.cli import main
from sf.integration import IntegrationError, plan_install
from sf.lifecycle import JOURNAL, execute_plan, plan_lifecycle, recover
from sf.adapters import declared_check_plan


def profile(root, *, name="input.json", commands=None, components=None):
    data = {"schemaVersion": 1, "project": {"id": "fixture"},
            "commands": commands if commands is not None else {},
            "components": components if components is not None else []}
    path = root / name
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def planned(root, mode, selected=None, *, ack=False):
    path = root / "saved-plan.json"
    path.write_text(json.dumps(plan_lifecycle(mode, root, selected, ack_manual=ack), sort_keys=True),
                    encoding="utf-8")
    return path


def snapshot(root):
    return {p.relative_to(root).as_posix():
            ("link", str(p.readlink())) if p.is_symlink() else
            ("dir",) if p.is_dir() else ("file", p.read_bytes())
            for p in root.rglob("*")}


class PortabilityTests(unittest.TestCase):
    def test_new_python_repository_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = profile(root, commands={"test": {"argv": ["forbidden-test-runner"], "cwd": "."}},
                        components=[{"id": "service", "path": ".", "stack": "python", "checks": ["test"]}])
            (root / "service.py").write_bytes(b"print('hello')\r\n")
            original = snapshot(root)
            with patch("subprocess.run", side_effect=AssertionError("project command executed")):
                self.assertFalse(plan_install(root, p)["releaseQualified"])
                self.assertEqual(snapshot(root), original)
                execute_plan(root, p, planned(root, "integrate", p), mode="integrate")
            self.assertEqual((root / "service.py").read_bytes(), b"print('hello')\r\n")
            self.assertEqual(execute_plan(root, p, planned(root, "integrate", p), mode="integrate")["status"], "no-op")
            execute_plan(root, None, planned(root, "remove"), mode="remove")
            self.assertFalse((root / ".s-f").exists())
            self.assertFalse((root / "AGENTS.md").exists())
            self.assertEqual((root / "service.py").read_bytes(), b"print('hello')\r\n")

    def test_existing_node_ui_with_custom_ci_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ui").mkdir()
            (root / "ui/package.json").write_bytes(b'{"scripts":{"test":"custom"}}\r\n')
            (root / "AGENTS.md").write_bytes(b"strict original\r\n")
            (root / "CLAUDE.md").write_bytes(b"original claude\n")
            (root / "ui/AGENTS.md").write_bytes(b"nested ownership\n")
            (root / ".github/workflows").mkdir(parents=True)
            (root / ".github/workflows/build.yml").write_bytes(b"name: custom\r\n")
            files = ["ui/package.json", "AGENTS.md", "CLAUDE.md",
                     "ui/AGENTS.md", ".github/workflows/build.yml"]
            before = {name: (root / name).read_bytes() for name in files}
            p = profile(root, commands={"check-ui": {"argv": ["npm", "test"], "cwd": "ui"}},
                        components=[{"id": "ui", "path": "ui", "stack": "node", "checks": ["check-ui"]}])
            self.assertFalse(plan_lifecycle("integrate", root, p)["ready"])
            self.assertTrue(plan_lifecycle("integrate", root, p, ack_manual=True)["ready"])
            execute_plan(root, p, planned(root, "integrate", p, ack=True), mode="integrate", ack_manual=True)
            execute_plan(root, None, planned(root, "remove"), mode="remove")
            for name, value in before.items():
                self.assertEqual((root / name).read_bytes(), value)

    def test_monorepo_with_dependency_order_and_no_executions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for directory, manifest in (("core", "Cargo.toml"), ("api", "pyproject.toml"), ("ui", "package.json")):
                (root / directory).mkdir()
                (root / directory / manifest).write_bytes(b"existing manifest")
            cmds = {name: {"argv": ["do-not-run", name], "cwd": where}
                    for name, where in (("build-core", "core"), ("build-api", "api"), ("build-ui", "ui"))}
            comps = [
                {"id": "ui", "path": "ui", "stack": "node", "dependsOn": ["api"], "checks": ["build-ui"]},
                {"id": "api", "path": "api", "stack": "python", "dependsOn": ["core"], "checks": ["build-api"]},
                {"id": "core", "path": "core", "stack": "rust", "checks": ["build-core"]},
            ]
            p = profile(root, commands=cmds, components=comps)
            ordered = declared_check_plan(json.loads(p.read_text()))
            self.assertEqual([entry["id"] for entry in ordered["orderedComponents"]], ["core", "api", "ui"])
            self.assertEqual(ordered["commandsExecuted"], [])
            before = snapshot(root)
            plan_lifecycle("integrate", root, p)
            self.assertEqual(snapshot(root), before)
            execute_plan(root, p, planned(root, "integrate", p), mode="integrate")
            for directory, manifest in (("core", "Cargo.toml"), ("api", "pyproject.toml"), ("ui", "package.json")):
                self.assertEqual((root / directory / manifest).read_bytes(), b"existing manifest")

    def test_custom_and_no_tests_never_claim_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Makefile").write_bytes(b"verify:\n\ttrue\n")
            p = profile(root, components=[{"id": "unknown", "path": ".", "stack": "custom"}])
            self.assertTrue(plan_lifecycle("integrate", root, p)["ready"])
            self.assertFalse(plan_lifecycle("integrate", root, p)["releaseQualified"])
            execute_plan(root, p, planned(root, "integrate", p), mode="integrate")
            self.assertEqual((root / "Makefile").read_bytes(), b"verify:\n\ttrue\n")

    def test_unicode_spaced_paths_and_nested_rules(self):
        with tempfile.TemporaryDirectory(prefix="source space-®-") as tmp:
            root = Path(tmp)
            (root / "sub project").mkdir()
            (root / "sub project/AGENTS.md").write_bytes(b"nested rules\r\n")
            p = profile(root, commands={"check": {"argv": ["make"], "cwd": "sub project"}},
                        components=[{"id": "svc", "path": "sub project", "stack": "custom", "checks": ["check"]}])
            execute_plan(root, p, planned(root, "integrate", p), mode="integrate")
            self.assertEqual((root / "sub project/AGENTS.md").read_bytes(), b"nested rules\r\n")

    def test_unknown_git_dirty_and_unrelated_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            (root / "local-change.txt").write_bytes(b"dirty local work")
            p = profile(root)
            result = plan_install(root, p)
            self.assertEqual(result["baseline"]["dirtyState"], "unknown")
            self.assertIsNone(result["baseline"]["gitTree"])
            self.assertEqual((root / "local-change.txt").read_bytes(), b"dirty local work")

    def test_nonowned_prefix_and_case_collision_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".s-f").mkdir()
            (root / ".s-f/unrelated.txt").write_bytes(b"private data")
            p = profile(root)
            self.assertFalse(plan_lifecycle("integrate", root, p)["ready"])
            self.assertEqual((root / ".s-f/unrelated.txt").read_bytes(), b"private data")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".S-F").mkdir()
            p = profile(root)
            self.assertFalse(plan_lifecycle("integrate", root, p)["ready"])

    def test_path_symlink_escape_blocks(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as elsewhere:
            root = Path(tmp)
            try:
                (root / ".s-f").symlink_to(elsewhere, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symlink capability missing on this operating system")
            p = profile(root)
            self.assertFalse(plan_lifecycle("integrate", root, p)["ready"])
            self.assertFalse((Path(elsewhere) / "profile.json").exists())

    def test_changed_profile_and_local_edit_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = profile(root)
            stale = planned(root, "integrate", p)
            (root / "AGENTS.md").write_bytes(b"new owner text")
            with self.assertRaises(IntegrationError):
                execute_plan(root, p, stale, mode="integrate")
            self.assertFalse((root / ".s-f").exists())
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = profile(root)
            execute_plan(root, p, planned(root, "integrate", p), mode="integrate")
            (root / ".s-f/INSTRUCTIONS.md").write_bytes(b"local policy modification")
            new = profile(root, name="new.json", commands={"check": {"argv": ["make", "new"], "cwd": "."}})
            self.assertFalse(plan_lifecycle("upgrade", root, new)["ready"])
            with self.assertRaises(IntegrationError):
                execute_plan(root, new, planned(root, "upgrade", new), mode="upgrade")
            self.assertEqual((root / ".s-f/INSTRUCTIONS.md").read_bytes(), b"local policy modification")

    def test_crash_requires_recovery_before_new_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = profile(root)
            saved = planned(root, "integrate", p)
            from sf import lifecycle
            real_effect = lifecycle._checked_effect
            count = []
            def interrupted(target, step):
                if count:
                    raise OSError("injected abrupt termination")
                count.append(step["path"])
                return real_effect(target, step)
            with patch("sf.lifecycle._checked_effect", side_effect=interrupted):
                with self.assertRaises(OSError):
                    execute_plan(root, p, saved, mode="integrate")
            self.assertTrue((root / JOURNAL).is_file())
            with self.assertRaises(IntegrationError):
                plan_lifecycle("integrate", root, p)
            self.assertEqual(recover(root)["status"], "completed")
            self.assertEqual(recover(root)["status"], "no-op")

    def test_cli_dry_run_and_apply(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = profile(root)
            capture = io.StringIO()
            with contextlib.redirect_stdout(capture):
                self.assertEqual(main(["integrate", "--dry-run", "--root", str(root),
                                       "--profile", str(p)]), 0)
            saved = root / "saved-plan.json"
            saved.write_text(capture.getvalue(), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["integrate", "--apply", str(saved), "--root", str(root),
                                       "--profile", str(p)]), 0)
            self.assertFalse(plan_lifecycle("remove", root)["releaseQualified"])
