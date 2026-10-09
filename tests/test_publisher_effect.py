"""Unit boundary tests: a mocked publisher observation is NOT live proof."""
from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sf.publisher import PublisherError
from sf.publisher_effect import authenticated_apply


class PublisherEffectTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.artifact = self.root / "bundle.zip"
        self.artifact.write_bytes(b"not a signed archive")
        self.digest = hashlib.sha256(self.artifact.read_bytes()).hexdigest()
        self.kwargs = dict(
            root=self.root, profile=self.root / "profile.json",
            plan=self.root / "plan.json", mode="integrate",
            artifact=self.artifact, trust=self.root / "trust.json",
            lock=self.root / "lock.json", release_pin=self.root / "pin.json",
            policy=self.root / "policy.json", expected_policy_sha256="a" * 64,
            attestation=self.root / "bundle.jsonl", verifier=self.root / "gh",
            trusted_root=self.root / "root.jsonl", minimum_release_epoch=4,
        )

    def proof(self):
        return {
            "status": "verified-by-operator-pinned-cli",
            "policySha256": "a" * 64, "artifactSha256": self.digest,
            "attestationSha256": "b" * 64, "installationAuthorized": False,
            "releaseQualified": False, "accepted": False,
        }

    def test_consumed_bytes_are_private_and_bound(self):
        with patch("sf.publisher_effect.authenticate_publisher", return_value=self.proof()):
            with patch("sf.publisher_effect.pinned.apply",
                       side_effect=self.inspect_apply) as apply:
                result = authenticated_apply(**self.kwargs)
        self.assertEqual(apply.call_count, 1)
        self.assertTrue(result["publisherVerificationObserved"])
        self.assertFalse(result["productionQualified"])
        self.assertFalse(result["releaseQualified"])
        self.assertFalse(result["independentPolicyCustodyVerified"])

    def inspect_apply(self, root, profile, plan, **params):
        bundle = params["bundle"]
        self.assertNotEqual(bundle, self.artifact)
        self.assertEqual(bundle.read_bytes(), self.artifact.read_bytes())
        self.assertEqual(params["mode"], "integrate")
        return {"status": "completed", "releaseQualified": False}

    def test_source_swap_after_verification_is_denied(self):
        def switch(*args, **kwargs):
            self.artifact.write_bytes(b"substituted archive")
            return self.proof()
        with patch("sf.publisher_effect.authenticate_publisher", side_effect=switch):
            with patch("sf.publisher_effect.pinned.apply") as apply:
                with self.assertRaises(PublisherError):
                    authenticated_apply(**self.kwargs)
                apply.assert_not_called()

    def test_verifier_rejects_before_install(self):
        with patch("sf.publisher_effect.authenticate_publisher",
                   side_effect=PublisherError("invalid attestation")):
            with patch("sf.publisher_effect.pinned.apply") as apply:
                with self.assertRaises(PublisherError):
                    authenticated_apply(**self.kwargs)
                apply.assert_not_called()

    def test_observation_cannot_assert_authority(self):
        for mutation in ({"accepted": True}, {"releaseQualified": True},
                         {"installationAuthorized": True},
                         {"status": "verified-by-candidate"},
                         {"policySha256": "c" * 64}):
            with self.subTest(mutation=mutation):
                proof = {**self.proof(), **mutation}
                with patch("sf.publisher_effect.authenticate_publisher", return_value=proof):
                    with patch("sf.publisher_effect.pinned.apply") as apply:
                        with self.assertRaises(PublisherError):
                            authenticated_apply(**self.kwargs)
                        apply.assert_not_called()

    def test_wrong_mode_never_calls_verifier(self):
        with patch("sf.publisher_effect.authenticate_publisher") as verify:
            with self.assertRaises(PublisherError):
                authenticated_apply(**{**self.kwargs, "mode": "remove"})
            verify.assert_not_called()

    def test_installer_failure_is_not_hidden(self):
        with patch("sf.publisher_effect.authenticate_publisher", return_value=self.proof()):
            with patch("sf.publisher_effect.pinned.apply",
                       side_effect=OSError("filesystem denied")):
                with self.assertRaises(OSError):
                    authenticated_apply(**self.kwargs)


if __name__ == "__main__":
    unittest.main()
