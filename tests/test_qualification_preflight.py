"""PQ-07F positive-reference completeness still yields explicit production NO-GO."""
import unittest

from sf.production_dossier import REQUIRED_CLAIMS
from sf.qualification_preflight import assess_preflight, PreflightError


SHA = "a" * 40
TREE = "b" * 40
ART = "c" * 64
POL = "d" * 64


def rows(state="present-unverified"):
    return [{"claim": x, "state": state} for x in REQUIRED_CLAIMS]


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.dossier = {
            "schemaVersion": 1, "kind": "sf-pq07a-dossier-gap-report",
            "candidate": {"sourceCommit": SHA, "sourceTree": TREE,
                          "artifactSha256": ART, "releaseId": "v1"},
            "scopeSupportedForReference": True, "claimStates": rows(),
            "accepted": False, "productionQualified": False,
            "externalIssuerAuthenticityVerified": False,
            "providerAndTargetEvidenceIndependentlyVerified": False,
        }
        self.policy = {
            "schemaVersion": 1, "kind": "sf-pq07b-policy-scope-observation",
            "policySha256": POL, "sourceScopeMatched": True,
            "accepted": False, "productionQualified": False,
            "releaseAuthorized": False, "externalClaimsVerified": False,
            "independentPolicyCustodyVerified": False,
        }
        self.audit = {
            "schemaVersion": 1, "kind": "sf-pq07d-retained-byte-audit",
            "artifactSha256": ART, "bytesRechecked": True,
            "accepted": False, "productionQualified": False,
            "releaseQualified": False, "signedProvenanceVerified": False,
            "independentPublisherCustodyVerified": False,
        }
        self.registry = {
            "schemaVersion": 1, "kind": "sf-pq07e-local-evidence-coverage",
            "sourceCommit": SHA, "artifactSha256": ART, "claimStates": rows(),
            "accepted": False, "productionQualified": False,
            "producerAuthenticityVerified": False,
            "independentAnchorVerified": False,
        }
        self.recovery = {
            "schemaVersion": 1, "kind": "sf-pq07c-recovery-assessment",
            "localClassification": "REFERENCE_EFFECT_PRESENT_UNVERIFIED",
            "retryAuthorized": False, "productionQualified": False,
            "targetReceiptAuthenticated": False,
            "remoteFenceQualified": False,
        }
        self.expect = {
            "expected_source_commit": SHA, "expected_source_tree": TREE,
            "expected_artifact_sha256": ART, "expected_policy_sha256": POL,
        }

    def call(self, **overrides):
        data = dict(dossier=self.dossier, policy=self.policy, audit=self.audit,
                    registry=self.registry, recovery=self.recovery, **self.expect)
        data.update(overrides)
        return assess_preflight(**data)

    def test_all_local_evidence_does_not_promote_to_production(self):
        out = self.call()
        self.assertTrue(out["referenceLocalRecordsPresent"])
        self.assertEqual(out["status"], "BLOCKED-external-qualification")
        self.assertEqual(out["SF_R10"], "UNMET-overall")
        self.assertGreater(len(out["externalQualificationBlockers"]), 5)
        for x in ("publisherAuthenticated", "deploymentQualified", "releaseAuthorized",
                  "publishAuthorized", "adopterPilotAuthorized", "productionQualified"):
            self.assertFalse(out[x])

    def test_missing_record_remains_no_go(self):
        self.registry["claimStates"][0]["state"] = "missing"
        result = self.call()
        self.assertFalse(result["referenceLocalRecordsPresent"])
        self.assertFalse(result["productionQualified"])

    def test_cross_artifact_and_source_substitution_rejected(self):
        with self.assertRaises(PreflightError):
            self.call(expected_artifact_sha256="e" * 64)
        self.registry["sourceCommit"] = "f" * 40
        with self.assertRaises(PreflightError):
            self.call()

    def test_candidate_authentication_flag_forgeries_rejected(self):
        self.audit["signedProvenanceVerified"] = True
        with self.assertRaises(PreflightError):
            self.call()
        self.audit["signedProvenanceVerified"] = False
        self.dossier["productionQualified"] = True
        with self.assertRaises(PreflightError):
            self.call()

    def test_unsupported_or_contradictory_recovery_rejected(self):
        self.recovery["localClassification"] = "CONTRADICTORY"
        with self.assertRaises(PreflightError):
            self.call()
        self.recovery["localClassification"] = "UNKNOWN_EFFECT"
        self.dossier["scopeSupportedForReference"] = False
        with self.assertRaises(PreflightError):
            self.call()

    def test_claim_oracle_cannot_be_truncated(self):
        self.registry["claimStates"].pop()
        with self.assertRaises(PreflightError):
            self.call()


if __name__ == "__main__":
    unittest.main()
