"""SF-13I: installer byte equality, negative trust, migration and recovery fixtures."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from sf.cli import main
from sf.distribution import MANDATORY, _canonical, build_bytes, verify_bundle
from sf.integration import IntegrationError
from sf.lifecycle import JOURNAL, execute_plan, plan_lifecycle, recover


def project_profile(root: Path, version: str = "a") -> Path:
    path = root / ("profile-" + version + ".json")
    path.write_text(json.dumps({
        "schemaVersion": 1, "project": {"id": "fixture"},
        "commands": {"check": {"argv": ["make", "test-" + version], "cwd": "."}},
        "components": [{"id": "service", "path": ".", "stack": "custom",
                        "checks": ["check"]}],
    }))
    return path


class PinnedLifecycleTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.source = self.tmp / "source"
        self.source.mkdir()
        self.project = self.tmp / "project"
        self.project.mkdir()
        self._git("init", "-q")
        self._git("config", "user.name", "Fixture")
        self._git("config", "user.email", "fixture@example.invalid")
        for name in sorted(MANDATORY):
            self._put(name, ("portable:" + name + "\n").encode())
        # Python source is not decoded as UTF-8 by the installer.
        self.module_bytes = b"portable-\xff-\x00\n"
        self._put("src/sf/module.py", self.module_bytes)
        self._git("add", ".")
        self._git("commit", "-qm", "source baseline")
        self.profile = project_profile(self.project)
        self.bundle, self.trust, self.lock = self._release("r1")

    def _git(self, *args):
        subprocess.run(["git", "-C", str(self.source), *args], stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, check=True)

    def _put(self, name: str, data: bytes):
        path = self.source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def _release(self, release: str):
        archive = build_bytes(self.source, publisher="fixture-publisher",
                              release_id=release)
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            m = json.loads(z.read("manifest.json"))
        pin = {
            "schemaVersion": 1, "kind": "sf-out-of-band-release-pin",
            "publisher": m["publisher"], "releaseId": m["releaseId"],
            "factoryVersion": m["factoryVersion"], "sourceCommit": m["sourceCommit"],
            "sourceTree": m["sourceTree"],
            "bundleSha256": hashlib.sha256(archive).hexdigest(),
            "expiresOn": "2099-01-01", "compatibility": m["compatibility"],
        }
        bundle = self.tmp / (release + ".zip")
        trust = self.tmp / (release + "-pin.json")
        lock = self.tmp / (release + "-lock.json")
        bundle.write_bytes(archive)
        trust.write_bytes(_canonical(pin))
        verify_bundle(bundle, trust, lock_out=lock)
        return bundle, trust, lock

    def _kwargs(self, release=None):
        b, t, l = release or (self.bundle, self.trust, self.lock)
        return {"bundle": b, "trust": t, "lock": l}

    def _plan(self, mode="integrate", profile=None, release=None, ack_manual=False):
        return plan_lifecycle(mode, self.project, profile if profile is not None else
                              (self.profile if mode != "remove" else None),
                              ack_manual=ack_manual,
                              **(self._kwargs(release) if mode != "remove" else {}))

    def _apply(self, mode="integrate", profile=None, release=None, ack_manual=False):
        selected_profile = profile if profile is not None else (
            self.profile if mode != "remove" else None)
        plan = self._plan(mode, selected_profile, release, ack_manual)
        doc = self.tmp / "saved-plan.json"
        doc.write_text(json.dumps(plan))
        return execute_plan(self.project, selected_profile, doc, mode=mode,
                            ack_manual=ack_manual,
                            **(self._kwargs(release) if mode != "remove" else {}))

    def _check_members(self, bundle: Path):
        with zipfile.ZipFile(bundle) as z:
            for member in z.namelist():
                if member == "manifest.json":
                    continue
                dest = self.project / ".s-f" / "portable" / member
                self.assertEqual(dest.read_bytes(), z.read(member), member)

    def test_install_preserves_binary_member_exactly(self):
        before = {p.relative_to(self.project).as_posix(): p.read_bytes()
                  for p in self.project.rglob("*") if p.is_file()}
        planned = self._plan()
        self.assertEqual(planned["schemaVersion"], 2)
        self.assertEqual(planned["verifiedLock"]["bundleSha256"],
                         hashlib.sha256(self.bundle.read_bytes()).hexdigest())
        self.assertFalse(planned["installedDistributionBytesVerified"])
        self.assertEqual(before, {p.relative_to(self.project).as_posix(): p.read_bytes()
                                  for p in self.project.rglob("*") if p.is_file()})
        receipt = self._apply()
        self.assertEqual(receipt["status"], "completed")
        self.assertTrue(receipt["installedDistributionBytesVerified"])
        self._check_members(self.bundle)
        self.assertEqual((self.project / ".s-f/portable/src/sf/module.py").read_bytes(),
                         self.module_bytes)
        self.assertFalse((self.project / JOURNAL).exists())

    def test_regular_cli_requires_three_proof_inputs(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["integrate", "--dry-run", "--root", str(self.project),
                                   "--profile", str(self.profile)]), 2)
        self.assertFalse((self.project / ".s-f").exists())

    def test_cli_pinned_install_round_trip(self):
        output = io.StringIO()
        kw = ["--bundle", str(self.bundle), "--trust", str(self.trust),
              "--lock", str(self.lock)]
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(["integrate", "--dry-run", "--root", str(self.project),
                                   "--profile", str(self.profile), *kw]), 0)
        doc = self.tmp / "cli-plan.json"
        doc.write_text(output.getvalue())
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["integrate", "--apply", str(doc), "--root", str(self.project),
                                   "--profile", str(self.profile), *kw]), 0)
        self._check_members(self.bundle)

    def test_no_write_for_missing_lock_or_unauthenticated_trust(self):
        self.lock.unlink()
        with self.assertRaises(Exception):
            self._plan()
        self.assertFalse((self.project / ".s-f").exists())
        self.lock.write_bytes(_canonical({
            "schemaVersion": 1, "kind": "sf-pinned-bundle-lock", "bad": "forgery"
        }))
        with self.assertRaises(Exception):
            self._plan()
        self.assertFalse((self.project / JOURNAL).exists())

    def test_corrupted_bundle_or_mismatched_lock_blocks_prewrite(self):
        self.bundle.write_bytes(self.bundle.read_bytes()[:-1] + b"Z")
        with self.assertRaises(Exception):
            self._apply()
        self.assertFalse((self.project / JOURNAL).exists())
        self.assertFalse((self.project / ".s-f").exists())

    def test_stale_proof_plan_never_authorizes_new_release(self):
        plan = self._plan()
        doc = self.tmp / "plan.json"
        doc.write_text(json.dumps(plan))
        self._put("src/sf/module.py", b"changed\n")
        self._git("add", ".")
        self._git("commit", "-qm", "new source")
        v2 = self._release("r2")
        with self.assertRaisesRegex(IntegrationError, "stale or altered"):
            execute_plan(self.project, self.profile, doc, mode="integrate", **self._kwargs(v2))
        self.assertFalse((self.project / JOURNAL).exists())
        self.assertFalse((self.project / ".s-f").exists())

    def test_upgrade_is_byte_exact_and_cannot_overwrite_user_modification(self):
        self._apply()
        self._check_members(self.bundle)
        self._put("src/sf/module.py", b"second-version\n")
        self._git("add", ".")
        self._git("commit", "-qm", "changed code")
        second = self._release("r2")
        next_profile = project_profile(self.project, "b")
        planned = self._plan("upgrade", next_profile, second)
        self.assertTrue(planned["ready"])
        receipt = self._apply("upgrade", next_profile, second)
        self.assertTrue(receipt["installedDistributionBytesVerified"])
        self._check_members(second[0])
        (self.project / ".s-f/portable/src/sf/module.py").write_bytes(b"local-edit")
        blocked = self._plan("upgrade", next_profile, second)
        self.assertFalse(blocked["ready"])
        self.assertIn(".s-f/portable/src/sf/module.py",
                      [row["path"] for row in blocked["conflicts"]])
        with self.assertRaises(IntegrationError):
            self._apply("upgrade", next_profile, second)
        self.assertEqual((self.project / ".s-f/portable/src/sf/module.py").read_bytes(),
                         b"local-edit")

    def test_interrupt_upgrade_recovery_uses_original_old_ownership(self):
        self._apply()
        self._put("src/sf/module.py", b"changed-after-restart\n")
        self._git("add", ".")
        self._git("commit", "-qm", "upgrade source")
        upgraded = self._release("r2")
        profile2 = project_profile(self.project, "b")
        planned = self._plan("upgrade", profile2, upgraded)
        doc = self.tmp / "upgrade.json"
        doc.write_text(json.dumps(planned))
        from sf import lifecycle
        effect = lifecycle._checked_effect
        seen = []
        def crash(root, step):
            if seen:
                raise OSError("crash after first effect")
            seen.append(step["path"])
            return effect(root, step)
        with patch("sf.lifecycle._checked_effect", side_effect=crash):
            with self.assertRaises(OSError):
                execute_plan(self.project, profile2, doc, mode="upgrade",
                             **self._kwargs(upgraded))
        self.assertTrue((self.project / JOURNAL).is_file())
        with self.assertRaises(Exception):
            recover(self.project)
        self.assertTrue((self.project / JOURNAL).is_file())
        result = recover(self.project, **self._kwargs(upgraded))
        self.assertEqual(result["status"], "completed")
        self._check_members(upgraded[0])

    def test_forged_recovery_steps_fail_closed(self):
        planned = self._plan()
        doc = self.tmp / "journal-prep.json"
        doc.write_text(json.dumps(planned))
        with patch("sf.lifecycle._checked_effect", side_effect=OSError("simulated kill")):
            with self.assertRaises(OSError):
                execute_plan(self.project, self.profile, doc, mode="integrate",
                             **self._kwargs())
        journal_file = self.project / JOURNAL
        self.assertTrue(journal_file.is_file())
        raw = json.loads(journal_file.read_text())
        raw["steps"][0]["path"] = "AGENTS.md" if raw["steps"][0]["path"] != "AGENTS.md" else "secret.txt"
        journal_file.write_text(json.dumps(raw))
        with self.assertRaises(IntegrationError):
            recover(self.project, **self._kwargs())
        self.assertTrue(journal_file.is_file())

    def test_manual_routing_preserves_custom_instructions_and_ci(self):
        (self.project / "AGENTS.md").write_bytes(b"KEEP-MY-RULES\r\n")
        (self.project / ".github/workflows").mkdir(parents=True)
        (self.project / ".github/workflows/project.yml").write_bytes(b"project-ci\r\n")
        planned = self._plan(ack_manual=True)
        self.assertTrue(planned["ready"])
        self._apply(ack_manual=True)
        self.assertEqual((self.project / "AGENTS.md").read_bytes(), b"KEEP-MY-RULES\r\n")
        self.assertEqual((self.project / ".github/workflows/project.yml").read_bytes(),
                         b"project-ci\r\n")
        self._check_members(self.bundle)

    def test_pinned_remove_preserves_foreign_files(self):
        self._apply()
        extra = self.project / ".s-f/portable/keep.txt"
        extra.write_bytes(b"not owned")
        result = self._apply("remove")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(extra.read_bytes(), b"not owned")
        self.assertFalse((self.project / ".s-f/OWNERSHIP.json").exists())
        self.assertFalse((self.project / ".s-f/FACTORY_LOCK.json").exists())
        self.assertFalse((self.project / "AGENTS.md").exists())

