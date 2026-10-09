"""PQ-07B policy pin, downgrade, scope, expiry, and self-trust tests."""
import hashlib
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sf.production_dossier import REQUIRED_CLAIMS
from sf.qualification_policy import PolicyError, assess_pinned_scope


def canonical(data):
    return (json.dumps(data, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True) + "\n").encode()


class PolicyIntakeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.dossier = {
            "schemaVersion": 1, "kind": "sf-pq07a-source-dossier",
            "candidate": {"sourceCommit": "a" * 40, "sourceTree": "b" * 40,
                          "artifactSha256": "c" * 64, "releaseId": "v1"},
            "profile": {"scopeId": "ref1", "platform": "linux",
                        "adapter": "disposable-single-host", "environment": "test"},
            "evidence": [], "excludedCapabilities": [],
        }
        self.policy = {
            "schemaVersion": 1, "kind": "sf-pq07-qualification-policy",
            "sourceCommit": "a" * 40, "sourceTree": "b" * 40,
            "artifactSha256": "c" * 64, "profile": self.dossier["profile"],
            "requiredClaims": list(REQUIRED_CLAIMS), "policyEpoch": 4,
            "expiresOn": "2099-01-01", "minimumEvidenceCount": len(REQUIRED_CLAIMS),
        }
        self.path = self.root / "policy.json"
        self.save()

    def save(self):
        self.path.write_bytes(canonical(self.policy))
        self.digest = hashlib.sha256(self.path.read_bytes()).hexdigest()

    def call(self, **overrides):
        args = dict(policy_path=self.path, expected_policy_sha256=self.digest,
                    dossier=self.dossier, minimum_policy_epoch=4,
                    today=date(2026, 10, 9))
        return assess_pinned_scope(**{**args, **overrides})

    def test_valid_pin_is_not_independent_custody(self):
        result = self.call()
        self.assertTrue(result["sourceScopeMatched"])
        self.assertFalse(result["allClaimsStructurallyPresent"])
        for key in ("independentPolicyCustodyVerified", "externalClaimsVerified",
                    "releaseAuthorized", "productionQualified", "accepted"):
            self.assertFalse(result[key])

    def test_operator_digest_substitution_denied(self):
        self.path.write_bytes(self.path.read_bytes() + b" ")
        with self.assertRaises(PolicyError):
            self.call()
        with self.assertRaises(PolicyError):
            self.call(expected_policy_sha256="f" * 64)

    def test_scope_mismatch_and_policy_downgrade_denied(self):
        self.dossier["candidate"]["sourceTree"] = "d" * 40
        with self.assertRaises(PolicyError):
            self.call()
        self.dossier["candidate"]["sourceTree"] = "b" * 40
        with self.assertRaises(PolicyError):
            self.call(minimum_policy_epoch=5)

    def test_expiry_and_claim_oracle_substitution_denied(self):
        with self.assertRaises(PolicyError):
            self.call(today=date(2100, 1, 1))
        self.policy["requiredClaims"].pop()
        self.save()
        with self.assertRaises(PolicyError):
            self.call()

    def test_extra_policy_field_and_duplicate_json_denied(self):
        self.policy["approve"] = True
        self.save()
        with self.assertRaises(PolicyError):
            self.call()
        raw = b'{"schemaVersion":1,"schemaVersion":1}'
        self.path.write_bytes(raw)
        with self.assertRaises(PolicyError):
            self.call(expected_policy_sha256=hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    unittest.main()
