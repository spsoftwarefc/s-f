"""PQ-01A unit contract tests. Mocked CLI success is NOT genuine publisher proof."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import subprocess
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from sf.cli import main
from sf.distribution import DistributionError, _canonical
from sf.publisher import PublisherError, _policy, authenticate_publisher


class PublisherAdapterTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.artifact = self._put("artifact.zip", b"synthetic archive bytes, not signed")
        self.attestation = self._put("attestation.jsonl", b'{"mock":true}\n')
        self.root_file = self._put("trusted-root.jsonl", b"synthetic-trust-root")
        self.verifier = self._put("gh-verifier", b"synthetic-verifier")
        self.pin = {
            "bundleSha256": self._sha(self.artifact.read_bytes()),
            "sourceCommit": "a" * 40, "sourceTree": "b" * 40,
            "releaseId": "preview1",
        }
        self.pin_file = self._put("pin.json", _canonical(self.pin))
        self.policy = {
            "schemaVersion": 1,
            "kind": "sf-github-public-publisher-policy",
            "repository": "spsoftwarefc/s-f",
            "signerWorkflow": "spsoftwarefc/s-f/.github/workflows/publish.yml",
            "signerDigest": "c" * 40,
            "sourceCommit": "a" * 40, "sourceTree": "b" * 40,
            "sourceRef": "refs/heads/main",
            "artifactSha256": self._sha(self.artifact.read_bytes()),
            "releaseId": "preview1", "releaseEpoch": 3,
            "verifierSha256": self._sha(self.verifier.read_bytes()),
            "trustedRootSha256": self._sha(self.root_file.read_bytes()),
            "expiresOn": "2099-01-01",
        }
        self.save_policy()

    def _sha(self, raw):
        return hashlib.sha256(raw).hexdigest()

    def _put(self, name, raw):
        p = self.root / name
        p.write_bytes(raw)
        return p

    def save_policy(self):
        self.policy_file = self._put("policy.json", _canonical(self.policy))
        self.policy_sha = self._sha(self.policy_file.read_bytes())

    def _call(self, **overrides):
        kw = {
            "artifact": self.artifact, "release_pin": self.pin_file,
            "policy_path": self.policy_file,
            "expected_policy_sha256": self.policy_sha,
            "attestation_path": self.attestation,
            "verifier_path": self.verifier,
            "trusted_root_path": self.root_file,
            "minimum_release_epoch": 2,
            "today": date(2026, 10, 9),
        }
        kw.update(overrides)
        return authenticate_publisher(**kw)

    def _verified_result(self, sha=None):
        return [{
            "verificationResult": {
                "statement": {
                    "predicateType": "https://slsa.dev/provenance/v1",
                    "subject": [{"name": "artifact.zip", "digest": {
                        "sha256": sha or self.policy["artifactSha256"]}}],
                }
            }
        }]

    def _mock_run(self, rows=None, code=0):
        return subprocess.CompletedProcess(
            args=[], returncode=code,
            stdout=json.dumps(rows if rows is not None else self._verified_result()).encode(),
            stderr=b"",
        )

    def test_matching_mock_result_never_claims_release_or_independent_custody(self):
        with patch("sf.publisher.verify_bytes", return_value={"lock": {"digest": "fixture"}}):
            with patch("sf.publisher.subprocess.run", return_value=self._mock_run()) as run:
                result = self._call()
        self.assertEqual(result["artifactSha256"], self.policy["artifactSha256"])
        self.assertEqual(result["status"], "verified-by-operator-pinned-cli")
        self.assertTrue(result["offlineVerifierReportedValid"])
        for field in ("independentPolicyCustodyVerified", "publisherAuthenticityQualified",
                      "releaseQualified", "installationAuthorized", "accepted"):
            self.assertFalse(result[field], field)
        args, kwargs = run.call_args
        self.assertIn("--repo", args[0])
        self.assertEqual(args[0][args[0].index("--repo") + 1], self.policy["repository"])
        for flag, expected in {
            "--signer-workflow": self.policy["signerWorkflow"],
            "--signer-digest": self.policy["signerDigest"],
            "--source-digest": self.policy["sourceCommit"],
            "--source-ref": self.policy["sourceRef"],
        }.items():
            self.assertEqual(args[0][args[0].index(flag) + 1], expected)
        self.assertEqual(kwargs["stdin"], subprocess.DEVNULL)
        self.assertNotIn("GH_TOKEN", kwargs["env"])
        self.assertNotIn("GITHUB_TOKEN", kwargs["env"])
        self.assertNotIn("CI", kwargs["env"])
        self.assertTrue(Path(args[0][3]).is_absolute())

    def test_candidate_policy_change_without_operator_digest_is_rejected(self):
        self.policy["repository"] = "attacker/other"
        self.policy_file.write_bytes(_canonical(self.policy))
        with self.assertRaisesRegex(PublisherError, "policy digest mismatch"):
            self._call()

    def test_wrong_expected_policy_digest_fails(self):
        with self.assertRaisesRegex(PublisherError, "policy digest mismatch"):
            self._call(expected_policy_sha256="0" * 64)

    def test_policy_canonical_and_extra_field_rejected(self):
        self.policy_file.write_text(json.dumps(self.policy))
        with self.assertRaisesRegex(PublisherError, "noncanonical"):
            self._call(expected_policy_sha256=self._sha(self.policy_file.read_bytes()))
        self.policy["unknownClaim"] = True
        self.save_policy()
        with self.assertRaisesRegex(PublisherError, "unsupported"):
            self._call()

    def test_expired_policy_and_unauthorized_downgrade(self):
        self.policy["expiresOn"] = "2020-01-01"
        self.save_policy()
        with self.assertRaisesRegex(PublisherError, "expired"):
            self._call()
        self.policy["expiresOn"] = "2099-01-01"
        self.save_policy()
        with self.assertRaisesRegex(PublisherError, "downgrade"):
            self._call(minimum_release_epoch=4)

    def test_wrong_signer_workflow_and_ref_rejected(self):
        self.policy["signerWorkflow"] = "attacker/other/.github/workflows/publish.yml"
        self.save_policy()
        with self.assertRaisesRegex(PublisherError, "signer workflow"):
            self._call()
        self.policy["signerWorkflow"] = "spsoftwarefc/s-f/.github/workflows/publish.yml"
        self.policy["sourceRef"] = "refs/heads/../wrong"
        self.save_policy()
        with self.assertRaisesRegex(PublisherError, "source ref"):
            self._call()

    def test_modified_artifact_rejected_before_verifier(self):
        self.artifact.write_bytes(b"wrong artifact")
        with self.assertRaisesRegex(PublisherError, "artifact differs"):
            self._call()

    def test_tampered_trusted_root_rejected(self):
        self.root_file.write_bytes(b"wrong root")
        with patch("sf.publisher.verify_bytes", return_value={"lock": {}}):
            with self.assertRaisesRegex(PublisherError, "trusted root digest mismatch"):
                self._call()

    def test_tampered_verifier_rejected_before_exec(self):
        self.verifier.write_bytes(b"malicious substitution")
        with patch("sf.publisher.verify_bytes", return_value={"lock": {}}):
            with patch("sf.publisher.subprocess.run") as run:
                with self.assertRaisesRegex(PublisherError, "verifier digest mismatch"):
                    self._call()
                run.assert_not_called()

    def test_symlink_policy_is_rejected(self):
        link = self.root / "policy-link"
        try:
            link.symlink_to(self.policy_file)
        except (OSError, NotImplementedError):
            # Skip only this platform-inapplicable assertion; no suite skip is emitted.
            return
        with self.assertRaisesRegex(PublisherError, "unsafe publisher policy"):
            self._call(policy_path=link)

    def test_invalid_release_pin_is_not_transformed_into_signature(self):
        with patch("sf.publisher.verify_bytes", side_effect=DistributionError("bad pin")):
            with self.assertRaisesRegex(PublisherError, "release pin rejected"):
                self._call()

    def test_conflicting_release_pin_is_rejected(self):
        self.pin["sourceCommit"] = "f" * 40
        self.pin_file.write_bytes(_canonical(self.pin))
        with patch("sf.publisher.verify_bytes", return_value={"lock": {}}):
            with self.assertRaisesRegex(PublisherError, "disagrees"):
                self._call()

    def test_cli_failed_nonzero_or_wrong_subject_is_rejected(self):
        with patch("sf.publisher.verify_bytes", return_value={"lock": {}}):
            with patch("sf.publisher.subprocess.run", return_value=self._mock_run(code=1)):
                with self.assertRaisesRegex(PublisherError, "rejected attestation"):
                    self._call()
            with patch("sf.publisher.subprocess.run", return_value=self._mock_run(
                    self._verified_result("0" * 64))):
                with self.assertRaisesRegex(PublisherError, "does not bind artifact"):
                    self._call()

    def test_cli_malformed_output_and_unavailable_executable_are_rejected(self):
        with patch("sf.publisher.verify_bytes", return_value={"lock": {}}):
            invalid = subprocess.CompletedProcess([], 0, b"not-json", b"")
            with patch("sf.publisher.subprocess.run", return_value=invalid):
                with self.assertRaisesRegex(PublisherError, "invalid verifier result"):
                    self._call()
            with patch("sf.publisher.subprocess.run", side_effect=OSError("no binary")):
                with self.assertRaisesRegex(PublisherError, "verifier unavailable"):
                    self._call()

    def test_distribution_cli_routes_read_only_authenticate(self):
        argv = [
            "distribution", "authenticate",
            "--artifact", str(self.artifact),
            "--release-pin", str(self.pin_file),
            "--policy", str(self.policy_file),
            "--attestation", str(self.attestation),
            "--verifier", str(self.verifier),
            "--trusted-root", str(self.root_file),
            "--policy-sha256", self.policy_sha,
            "--minimum-release-epoch", "2",
        ]
        buf = io.StringIO()
        with patch("sf.cli.authenticate_publisher", return_value={
                "accepted": False, "releaseQualified": False}) as fn:
            with contextlib.redirect_stdout(buf):
                status = main(argv)
        self.assertEqual(status, 0)
        self.assertFalse(json.loads(buf.getvalue())["accepted"])
        self.assertEqual(fn.call_args.kwargs["minimum_release_epoch"], 2)


if __name__ == "__main__":
    unittest.main()
