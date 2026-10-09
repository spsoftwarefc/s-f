"""PQ-07P exact byte bridge negative and source-boundary tests."""
import hashlib
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from sf.retained_artifact import _canonical, stage_retained
from sf.retained_publisher import RetainedPublisherError, review_retained_publisher


class RetainedPublisherTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.store = self.root / "store"
        self.store.mkdir()
        self.source = self.root / "source.zip"
        self.source.write_bytes(b"source-bound preview artifact")
        self.sha = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.policy_sha = "e" * 64
        self.manifest = {
            "schemaVersion": 1, "kind": "sf-reference-retained-build",
            "releaseId": "v1", "artifactSha256": self.sha,
            "sourceCommit": "a" * 40, "sourceTree": "b" * 40,
            "toolchainSha256": "c" * 64, "sbomSha256": "d" * 64,
            "provenanceSha256": "e" * 64, "retainUntil": "2099-01-01",
        }
        stage_retained(self.source, self.store, self.manifest, today=date(2026, 10, 9))
        self.manifest_sha = hashlib.sha256(_canonical(self.manifest)).hexdigest()
        self.options = dict(release_pin=self.source, policy=self.source,
                            policy_sha256=self.policy_sha, attestation=self.source,
                            verifier=self.source, trusted_root=self.source,
                            minimum_release_epoch=1, today=date(2026, 10, 9))

    def proof(self):
        return {"status": "verified-by-operator-pinned-cli",
                "artifactSha256": self.sha, "policySha256": self.policy_sha,
                "sourceCommit": "a" * 40, "sourceTree": "b" * 40,
                "independentPolicyCustodyVerified": False,
                "publisherAuthenticityQualified": False,
                "installationAuthorized": False, "releaseQualified": False,
                "accepted": False, "attestationSha256": "f" * 64}

    def call(self, manifest_sha=None):
        return review_retained_publisher(self.store, self.sha,
                                         manifest_sha or self.manifest_sha,
                                         **self.options)

    def test_exact_consumed_bytes_and_all_release_flags_false(self):
        def authenticate(artifact, *args, **kwargs):
            self.assertEqual(artifact.read_bytes(), self.source.read_bytes())
            self.assertNotEqual(artifact, self.source)
            return self.proof()
        with patch("sf.retained_publisher.authenticate_publisher", side_effect=authenticate):
            result = self.call()
        self.assertTrue(result["exactRetainedBytesObserved"])
        self.assertFalse(result["productionQualified"])
        self.assertFalse(result["installationAuthorized"])

    def test_manifest_pin_must_match_before_authentication(self):
        with patch("sf.retained_publisher.authenticate_publisher") as auth:
            with self.assertRaises(RetainedPublisherError):
                self.call("f" * 64)
            auth.assert_not_called()

    def test_tampered_retention_denied(self):
        (self.store / (self.sha + ".zip")).write_bytes(b"attacker bytes")
        with patch("sf.retained_publisher.authenticate_publisher") as auth:
            with self.assertRaises(RetainedPublisherError):
                self.call()
            auth.assert_not_called()

    def test_false_publisher_authority_and_wrong_tree_denied(self):
        for change in ({"accepted": True}, {"releaseQualified": True},
                       {"sourceTree": "f" * 40}, {"artifactSha256": "a" * 64}):
            with self.subTest(change=change):
                with patch("sf.retained_publisher.authenticate_publisher",
                           return_value={**self.proof(), **change}):
                    with self.assertRaises(RetainedPublisherError):
                        self.call()


if __name__ == "__main__":
    unittest.main()
