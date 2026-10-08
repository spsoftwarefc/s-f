"""SF-14: source, artifact, CI, authorization and recovery release-plan fixtures."""
from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import subprocess
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sf.cli import main
from sf.release import ReleasePlanError, plan_release


def canonical(data):
    return (json.dumps(data, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True) + "\n").encode("utf-8")


def digest(data):
    return hashlib.sha256(data).hexdigest()


class ReleasePlanningTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.root = self.folder / "repo"
        self.root.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Release Fixture")
        self.git("config", "user.email", "release@example.invalid")
        (self.root / "docs").mkdir()
        (self.root / "docs/migration.txt").write_bytes(b"schema migration v1\n")
        (self.root / "docs/recovery.txt").write_bytes(b"restore previous fixture\n")
        (self.root / "source.py").write_bytes(b"x = 7\n")
        self.git("add", ".")
        self.git("commit", "-qm", "accepted source fixture")
        self.commit = self.git("rev-parse", "HEAD")
        self.tree = self.git("rev-parse", "HEAD^{tree}")
        self.artifact = self.folder / "artifact.bin"
        self.artifact.write_bytes(b"opaque-release-artifact-\xff\x00\n")
        self.ci = self.folder / "ci.json"
        self.ci.write_bytes(canonical({
            "schemaVersion": 1, "source": "github",
            "status": "provider-metadata-verified", "providerMetadataVerified": True,
            "accepted": False, "candidateSha": self.commit,
            "runId": 1001, "attempt": 1,
            "boundary": {"checkoutShaProviderAttested": False},
        }))
        self.request = self.folder / "release-request.json"
        self.approval = self.folder / "externally-approved-pin.json"
        self.data = {
            "schemaVersion": 1, "kind": "sf-release-plan-request",
            "source": {"repository": "example/sandbox", "commit": self.commit, "tree": self.tree},
            "artifact": {"kind": "archive", "sha256": digest(self.artifact.read_bytes())},
            "ci": {"receiptSha256": digest(self.ci.read_bytes()),
                   "runId": 1001, "attempt": 1},
            "destination": {"targetId": "sandbox-1", "environment": "staging",
                            "adapter": "fixture"},
            "authorization": {"principal": "operator-1", "grantId": "grant-100",
                              "expiresOn": "2099-01-01"},
            "migration": {"path": "docs/migration.txt",
                          "sha256": digest((self.root / "docs/migration.txt").read_bytes()),
                          "disposition": "forward"},
            "recovery": {"path": "docs/recovery.txt",
                         "sha256": digest((self.root / "docs/recovery.txt").read_bytes()),
                         "disposition": "restore"},
        }
        self.save()

    def git(self, *args):
        p = subprocess.run(["git", "-C", str(self.root), *args],
                           capture_output=True, text=True, check=True)
        return p.stdout.strip()

    def save(self):
        raw = canonical(self.data)
        self.request.write_bytes(raw)
        pin = {
            "schemaVersion": 1, "kind": "sf-externally-approved-release-pin",
            "requestSha256": digest(raw),
            "sourceCommit": self.data["source"]["commit"],
            "sourceTree": self.data["source"]["tree"],
            "ciSha256": self.data["ci"]["receiptSha256"],
            "artifactSha256": self.data["artifact"]["sha256"],
            "destination": copy.deepcopy(self.data["destination"]),
            "grantId": self.data["authorization"]["grantId"],
            "expiresOn": self.data["authorization"]["expiresOn"],
            "migrationSha256": self.data["migration"]["sha256"],
            "recoverySha256": self.data["recovery"]["sha256"],
        }
        self.approval.write_bytes(canonical(pin))

    def plan(self, **kwargs):
        return plan_release(self.root, self.request, self.artifact, self.ci,
                            self.approval, today=date(2026, 10, 8), **kwargs)

    def test_exact_approval_is_deterministic_and_read_only(self):
        before = [(p.relative_to(self.root).as_posix(), p.read_bytes())
                  for p in self.root.rglob("*") if p.is_file() and ".git" not in p.parts]
        one = self.plan()
        self.assertEqual(one, self.plan())
        self.assertEqual(one["source"]["commit"], self.commit)
        self.assertEqual(one["source"]["tree"], self.tree)
        self.assertEqual(one["artifact"]["sha256"], digest(self.artifact.read_bytes()))
        self.assertEqual(one["destination"]["environment"], "staging")
        self.assertTrue(one["sourceCheckoutVerified"])
        self.assertFalse(one["approvedReleaseOriginAuthenticated"])
        self.assertFalse(one["deploymentAuthorized"])
        self.assertFalse(one["releaseQualified"])
        after = [(p.relative_to(self.root).as_posix(), p.read_bytes())
                 for p in self.root.rglob("*") if p.is_file() and ".git" not in p.parts]
        self.assertEqual(before, after)

    def test_cli_release_plan(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.assertEqual(main(["release", "plan", "--root", str(self.root),
                                   "--request", str(self.request),
                                   "--artifact", str(self.artifact),
                                   "--ci-receipt", str(self.ci),
                                   "--approval-pin", str(self.approval)]), 0)
        result = json.loads(buffer.getvalue())
        self.assertFalse(result["deploymentAuthorized"])
        self.assertEqual(result["artifact"]["kind"], "archive")

    def test_changed_artifact_rejected_even_when_local_pin_matches_original(self):
        self.artifact.write_bytes(b"mutated artifact")
        with self.assertRaisesRegex(ReleasePlanError, "artifact bytes"):
            self.plan()

    def test_untrusted_forged_candidate_acceptance_rejected(self):
        fake = json.loads(self.ci.read_text())
        fake["accepted"] = True
        self.ci.write_bytes(canonical(fake))
        self.data["ci"]["receiptSha256"] = digest(self.ci.read_bytes())
        self.save()  # Even a matching locally fabricated pin cannot promote SF10.
        with self.assertRaisesRegex(ReleasePlanError, "CI receipt missing"):
            self.plan()

    def test_ci_receipt_run_or_source_mismatch_rejected(self):
        fake = json.loads(self.ci.read_text())
        fake["candidateSha"] = "0" * 40
        self.ci.write_bytes(canonical(fake))
        self.data["ci"]["receiptSha256"] = digest(self.ci.read_bytes())
        self.save()
        with self.assertRaisesRegex(ReleasePlanError, "CI receipt missing"):
            self.plan()

    def test_external_pin_fails_on_altered_destination(self):
        self.data["destination"]["targetId"] = "different"
        self.request.write_bytes(canonical(self.data))
        with self.assertRaisesRegex(ReleasePlanError, "external approval pin disagrees"):
            self.plan()

    def test_expired_authorization_fails_even_with_matching_pin(self):
        self.data["authorization"]["expiresOn"] = "2020-01-01"
        self.save()
        with self.assertRaisesRegex(ReleasePlanError, "expired"):
            self.plan()

    def test_source_commit_tree_mismatch_rejected(self):
        self.data["source"]["commit"] = "f" * 40
        self.save()
        with self.assertRaisesRegex(ReleasePlanError, "source commit/tree"):
            self.plan()

    def test_dirty_source_is_not_accepted(self):
        (self.root / "untracked.txt").write_text("unknown input")
        with self.assertRaisesRegex(ReleasePlanError, "dirty"):
            self.plan()

    def test_migration_or_recovery_file_tampering_blocks(self):
        for name in ("migration", "recovery"):
            with self.subTest(name=name):
                path = self.root / self.data[name]["path"]
                original = path.read_bytes()
                path.write_bytes(b"tampered plan")
                with self.assertRaises(ReleasePlanError):
                    self.plan()
                path.write_bytes(original)

    def test_wrong_pinned_recovery_digest_rejected(self):
        self.data["recovery"]["sha256"] = "0" * 64
        self.save()
        with self.assertRaisesRegex(ReleasePlanError, "digest differs"):
            self.plan()

    def test_duplicate_request_json_is_rejected(self):
        self.request.write_bytes(b'{"schemaVersion":1,"schemaVersion":1}')
        with self.assertRaisesRegex(ReleasePlanError, "duplicate"):
            self.plan()

    def test_unknown_fields_cannot_expand_authorization(self):
        self.data["releaseReady"] = True
        self.save()
        with self.assertRaisesRegex(ReleasePlanError, "unknown or missing"):
            self.plan()

    def test_invalid_target_and_path_rejected(self):
        self.data["destination"]["targetId"] = "../outside"
        self.save()
        with self.assertRaisesRegex(ReleasePlanError, "invalid identity"):
            self.plan()

    def test_missing_artifact_is_rejected(self):
        self.artifact.unlink()
        with self.assertRaises(ReleasePlanError):
            self.plan()

    def test_symlinked_artifact_is_rejected_without_following_it(self):
        actual = self.folder / "real-artifact.bin"
        actual.write_bytes(self.artifact.read_bytes())
        self.artifact.unlink()
        try:
            self.artifact.symlink_to(actual)
        except (OSError, NotImplementedError):
            return
        with self.assertRaises(ReleasePlanError):
            self.plan()
