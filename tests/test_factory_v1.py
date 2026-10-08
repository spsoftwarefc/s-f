"""SF-19: integrated source archive -> install -> release -> fake deploy -> ops."""
from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import subprocess
import tempfile
import unittest
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

from sf.cli import main
from sf.distribution import MANDATORY, _canonical, build_bytes, verify_bundle
from sf.lifecycle import JOURNAL, execute_plan, plan_lifecycle, recover
from sf.qualification import QualificationError, qualify_factory
from sf.release import plan_release
from sf.deployment import qualify_deployment
from sf.operations import assess_operations


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value) -> bytes:
    return _canonical(value)


class FactoryV1Tests(unittest.TestCase):
    """Fixtures are independent Git source and target trees, never a live repo."""

    def setUp(self):
        hold = tempfile.TemporaryDirectory()
        self.addCleanup(hold.cleanup)
        self.tmp = Path(hold.name)
        self.source = self.tmp / "source"
        self.source.mkdir()
        self.target = self.tmp / "target"
        self.target.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Factory Test")
        self.git("config", "user.email", "fixture@example.invalid")
        for name in sorted(MANDATORY):
            self.put(name, ("portable:" + name + "\n").encode())
        self.put("src/sf/synthetic_binary.py", b"binary-\x00-\xff\r\n")
        self.put("docs/migration.txt", b"fixture migration only\n")
        self.put("docs/recovery.txt", b"fixture recovery only\n")
        self.git("add", ".")
        self.git("commit", "-qm", "source fixture")
        self.commit = self.git("rev-parse", "HEAD")
        self.tree = self.git("rev-parse", "HEAD^{tree}")
        self.profile = self.target / "profile.json"
        self.profile.write_text(json.dumps({
            "schemaVersion": 1, "project": {"id": "fixture"},
            "commands": {"check": {"argv": ["make", "fake"], "cwd": "."}},
            "components": [{"id": "service", "path": ".", "stack": "custom",
                            "checks": ["check"]}],
        }))
        (self.target / "AGENTS.md").write_bytes(b"EXISTING-PROJECT-RULES\r\n")
        (self.target / ".github/workflows").mkdir(parents=True)
        (self.target / ".github/workflows/original.yml").write_bytes(b"project-policy\r\n")
        self.original_instructions = (self.target / "AGENTS.md").read_bytes()
        self.original_ci = (self.target / ".github/workflows/original.yml").read_bytes()
        self.bundle, self.trust, self.lock = self.archive("one")
        self.install()
        self.now = datetime(2026, 10, 8, 20, 0, 20, tzinfo=timezone.utc)
        self.make_release_chain()

    def git(self, *args):
        result = subprocess.run(["git", "-C", str(self.source), *args],
                                capture_output=True, text=True, check=True)
        return result.stdout.strip()

    def put(self, name: str, raw: bytes):
        path = self.source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)

    def archive(self, version: str):
        raw = build_bytes(self.source, publisher="fixture-publisher",
                          release_id=version)
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            manifest = json.loads(z.read("manifest.json"))
        pin = {
            "schemaVersion": 1, "kind": "sf-out-of-band-release-pin",
            "publisher": manifest["publisher"], "releaseId": manifest["releaseId"],
            "factoryVersion": manifest["factoryVersion"],
            "sourceCommit": manifest["sourceCommit"], "sourceTree": manifest["sourceTree"],
            "bundleSha256": digest(raw), "expiresOn": "2099-01-01",
            "compatibility": manifest["compatibility"],
        }
        archive = self.tmp / (version + ".zip")
        trust = self.tmp / (version + ".json")
        lock = self.tmp / (version + ".lock.json")
        archive.write_bytes(raw)
        trust.write_bytes(canonical(pin))
        verify_bundle(archive, trust, lock_out=lock)
        return archive, trust, lock

    def proof(self):
        return {"bundle": self.bundle, "trust": self.trust, "lock": self.lock}

    def perform(self, mode: str = "integrate", profile: Path | None = None):
        prof = profile or (self.profile if mode != "remove" else None)
        proof = self.proof() if mode != "remove" else {}
        plan = plan_lifecycle(mode, self.target, prof, ack_manual=True, **proof)
        self.assertTrue(plan["ready"], plan["conflicts"])
        path = self.tmp / ("saved-" + mode + ".json")
        path.write_text(json.dumps(plan))
        return execute_plan(self.target, prof, path, mode=mode, ack_manual=True, **proof)

    def install(self):
        result = self.perform()
        self.assertEqual(result["status"], "completed")

    def make_release_chain(self):
        self.ci_file = self.tmp / "ci-claim.json"
        self.ci_file.write_bytes(canonical({
            "schemaVersion": 1, "source": "github",
            "status": "provider-metadata-verified", "providerMetadataVerified": True,
            "accepted": False, "candidateSha": self.commit,
            "runId": 321, "attempt": 1,
        }))
        self.release_request = self.tmp / "release-request.json"
        self.approval = self.tmp / "local-approval-claim.json"
        self.release_data = {
            "schemaVersion": 1, "kind": "sf-release-plan-request",
            "source": {"repository": "example/fake-source", "commit": self.commit,
                       "tree": self.tree},
            "artifact": {"kind": "archive", "sha256": digest(self.bundle.read_bytes())},
            "ci": {"receiptSha256": digest(self.ci_file.read_bytes()),
                   "runId": 321, "attempt": 1},
            "destination": {"targetId": "fake-target", "environment": "fixture",
                            "adapter": "inmemory"},
            "authorization": {"principal": "operator-1", "grantId": "grant-321",
                              "expiresOn": "2099-01-01"},
            "migration": {"path": "docs/migration.txt",
                          "sha256": digest((self.source / "docs/migration.txt").read_bytes()),
                          "disposition": "forward"},
            "recovery": {"path": "docs/recovery.txt",
                         "sha256": digest((self.source / "docs/recovery.txt").read_bytes()),
                         "disposition": "restore"},
        }
        request = canonical(self.release_data)
        self.release_request.write_bytes(request)
        self.approval.write_bytes(canonical({
            "schemaVersion": 1, "kind": "sf-externally-approved-release-pin",
            "requestSha256": digest(request),
            "sourceCommit": self.commit, "sourceTree": self.tree,
            "ciSha256": digest(self.ci_file.read_bytes()),
            "artifactSha256": digest(self.bundle.read_bytes()),
            "destination": self.release_data["destination"],
            "grantId": self.release_data["authorization"]["grantId"],
            "expiresOn": self.release_data["authorization"]["expiresOn"],
            "migrationSha256": self.release_data["migration"]["sha256"],
            "recoverySha256": self.release_data["recovery"]["sha256"],
        }))
        self.release = plan_release(self.source, self.release_request, self.bundle,
                                    self.ci_file, self.approval, today=date(2026, 10, 8))
        self.deployment = qualify_deployment(self.release, today=self.now.date())
        self.assertEqual(self.deployment["scenariosPassed"], 12)
        self.policy = {
            "schemaVersion": 1, "kind": "sf16-operations-policy",
            "sourceCommit": self.commit, "planSha256": self.deployment["planSha256"],
            "destination": copy.deepcopy(self.release_data["destination"]),
            "maxEventAgeSeconds": 300, "maxEvents": 12, "recoveryHealthyCount": 2,
            "routes": {domain: {"ownerId": "oncall-" + domain, "runbookId": "rb-" + domain}
                       for domain in ("deployment", "health", "migration", "recovery")},
        }
        self.observations = {
            "schemaVersion": 1, "kind": "sf16-offline-observations",
            "sourceCommit": self.commit, "planSha256": self.deployment["planSha256"],
            "destination": copy.deepcopy(self.release_data["destination"]),
            "events": [
                {"eventId": "obs-" + domain, "observedAt": "2026-10-08T20:00:10Z",
                 "domain": domain, "state": "healthy",
                 "evidenceSha256": "a" * 64}
                for domain in ("deployment", "health", "migration", "recovery")
            ],
        }

    def qualify(self, **changes):
        args = {
            "target": self.target, "bundle": self.bundle, "trust": self.trust,
            "lock": self.lock, "release_plan": self.release,
            "deployment_report": self.deployment, "policy": self.policy,
            "observations": self.observations, "now": self.now,
        }
        args.update(changes)
        return qualify_factory(**args)

    def test_full_integrated_fixture_source_bytes_through_operations(self):
        original = {p.relative_to(self.target).as_posix(): p.read_bytes()
                    for p in self.target.rglob("*") if p.is_file()}
        result = self.qualify()
        self.assertTrue(result["developmentFixturePassed"])
        self.assertTrue(result["installedOwnedBytesRechecked"])
        self.assertEqual(result["operationsDisposition"], "healthy-observed-unverified")
        self.assertEqual(result["syntheticScenariosPassed"], 12)
        for flag in ("productionReady", "releaseQualified", "accepted",
                     "mergeAuthorized", "deploymentAuthorized", "realDeploymentExercised",
                     "publisherAuthenticityVerified", "externalReleaseAuthorityVerified",
                     "liveOperationsVerified", "durableRecoveryVerified",
                     "independentCIVerified"):
            self.assertIs(result[flag], False)
        self.assertEqual(self.original_instructions, (self.target / "AGENTS.md").read_bytes())
        self.assertEqual(self.original_ci, (self.target / ".github/workflows/original.yml").read_bytes())
        self.assertEqual(original, {p.relative_to(self.target).as_posix(): p.read_bytes()
                                   for p in self.target.rglob("*") if p.is_file()})

    def test_installed_binary_payload_byte_identity(self):
        self.assertEqual((self.target / ".s-f/portable/src/sf/synthetic_binary.py").read_bytes(),
                         b"binary-\x00-\xff\r\n")
        self.assertTrue(self.qualify()["installedOwnedBytesRechecked"])

    def test_changed_managed_file_fails_even_when_manifests_remain(self):
        path = self.target / ".s-f/portable/src/sf/synthetic_binary.py"
        path.write_bytes(b"attack")
        with self.assertRaisesRegex(QualificationError, "installed factory owned member mismatch"):
            self.qualify()

    def test_changed_generated_owned_file_fails(self):
        (self.target / ".s-f/INSTRUCTIONS.md").write_text("forged policy")
        with self.assertRaises(QualificationError):
            self.qualify()

    def test_modified_manifest_or_install_record_fails(self):
        (self.target / ".s-f/FACTORY_LOCK.json").write_text('{"malformed":true}')
        with self.assertRaises(QualificationError):
            self.qualify()

    def test_mismatched_bundle_or_expired_pin_blocks_claim(self):
        self.bundle.write_bytes(self.bundle.read_bytes() + b"tamper")
        with self.assertRaises(QualificationError):
            self.qualify()

    def test_missing_lock_does_not_promote_source(self):
        self.lock.unlink()
        with self.assertRaises(QualificationError):
            self.qualify()

    def test_rejected_release_source_substitution(self):
        forged = copy.deepcopy(self.release)
        forged["source"]["commit"] = "0" * 40
        with self.assertRaises(QualificationError):
            self.qualify(release_plan=forged)

    def test_rejected_release_artifact_mismatch(self):
        forged = copy.deepcopy(self.release)
        forged["artifact"]["sha256"] = "0" * 64
        with self.assertRaises(QualificationError):
            self.qualify(release_plan=forged)

    def test_rejected_spoofed_deployment_report(self):
        fake = copy.deepcopy(self.deployment)
        fake["syntheticScenariosPassed"] = 0
        with self.assertRaises(QualificationError):
            self.qualify(deployment_report=fake)

    def test_rejected_spoofed_deployment_authority(self):
        fake = copy.deepcopy(self.deployment)
        fake["deploymentAuthorized"] = True
        with self.assertRaises(QualificationError):
            self.qualify(deployment_report=fake)

    def test_changed_operations_destination_rejected(self):
        o = copy.deepcopy(self.observations)
        o["destination"]["targetId"] = "wrong-target"
        with self.assertRaises(QualificationError):
            self.qualify(observations=o)

    def test_unknown_operations_remain_unknown_not_release_ready(self):
        o = copy.deepcopy(self.observations)
        o["events"] = []
        result = self.qualify(observations=o)
        self.assertEqual(result["operationsDisposition"], "observation-incomplete")
        self.assertFalse(result["productionReady"])

    def test_anomalous_operations_only_propose_work_not_resolve(self):
        o = copy.deepcopy(self.observations)
        o["events"][0]["state"] = "failed"
        result = self.qualify(observations=o)
        self.assertEqual(result["operationsDisposition"], "incident-review-required")
        self.assertEqual(result["operationsIncidents"], 1)
        self.assertEqual(result["operationsProposals"], 1)
        self.assertFalse(result["releaseQualified"])

    def test_unsettled_installation_recovery_fails_closed(self):
        journal = self.target / JOURNAL
        journal.write_text("{}")
        with self.assertRaises(QualificationError):
            self.qualify()
        journal.unlink()
        self.assertTrue(self.qualify()["developmentFixturePassed"])

    def test_upgrade_rebinds_exact_archive_then_previous_fails(self):
        old = (self.bundle, self.trust, self.lock, self.release, self.deployment,
               self.policy, self.observations)
        self.put("src/sf/synthetic_binary.py", b"second-version\n")
        self.git("add", ".")
        self.git("commit", "-qm", "upgrade committed source")
        self.commit, self.tree = self.git("rev-parse", "HEAD"), self.git("rev-parse", "HEAD^{tree}")
        self.bundle, self.trust, self.lock = self.archive("two")
        self.perform("upgrade")
        with self.assertRaises(QualificationError):
            self.qualify(bundle=old[0], trust=old[1], lock=old[2],
                         release_plan=old[3], deployment_report=old[4],
                         policy=old[5], observations=old[6])
        self.make_release_chain()
        self.assertTrue(self.qualify()["developmentFixturePassed"])

    def test_after_remove_no_installed_factory_claim_and_foreign_preserved(self):
        self.perform("remove")
        self.assertFalse((self.target / ".s-f/FACTORY_LOCK.json").exists())
        with self.assertRaises(QualificationError):
            self.qualify()
        self.assertEqual(self.original_instructions, (self.target / "AGENTS.md").read_bytes())
        self.assertEqual(self.original_ci, (self.target / ".github/workflows/original.yml").read_bytes())

    def test_cli_integrated_qualification_is_read_only_and_never_authorizes(self):
        docs = [
            ("release-plan", self.release),
            ("deployment", self.deployment),
            ("operations-policy", self.policy),
            ("observations", self.observations),
        ]
        arguments = ["factory", "qualify", "--target", str(self.target),
                     "--bundle", str(self.bundle), "--trust", str(self.trust),
                     "--lock", str(self.lock),
                     "--as-of", "2026-10-08T20:00:20Z"]
        for name, data in docs:
            path = self.tmp / (name + ".json")
            path.write_bytes(canonical(data))
            arguments.extend(["--" + name, str(path)])
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(arguments), 0)
        result = json.loads(output.getvalue())
        self.assertFalse(result["productionReady"])
        self.assertFalse(result["mergeAuthorized"])
        self.assertTrue(result["readOnly"])
        arguments[-1] = str(self.tmp / "missing-observations.json")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(arguments), 2)

    def test_cli_invalid_timestamp_rejected(self):
        docs = [("release-plan", self.release), ("deployment", self.deployment),
                ("operations-policy", self.policy), ("observations", self.observations)]
        args = ["factory", "qualify", "--target", str(self.target),
                "--bundle", str(self.bundle), "--trust", str(self.trust),
                "--lock", str(self.lock), "--as-of", "not-utc"]
        for name, data in docs:
            p = self.tmp / (name + ".json")
            p.write_bytes(canonical(data))
            args.extend(["--" + name, str(p)])
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(args), 2)


if __name__ == "__main__":
    unittest.main()
