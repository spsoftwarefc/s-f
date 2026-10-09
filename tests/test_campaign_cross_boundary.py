"""PQ-07K: end-to-end local completeness cannot manufacture PQ-07/PQ-08 authority."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from sf.campaign_intake import inspect_campaign
from sf.external_readiness import (
    ExternalReadinessError, REQUIRED_DECISIONS, inspect_external_decisions,
)
from sf.production_dossier import REQUIRED_CLAIMS
from sf.qualification_preflight import PreflightError, assess_preflight


SOURCE = "a" * 40
TREE = "b" * 40
ARTIFACT = "c" * 64
POLICY = "d" * 64
PROFILE = {"scopeId": "reference", "platform": "linux",
           "adapter": "disposable-single-host", "environment": "test"}


def canonical(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=True,
                       allow_nan=False, separators=(",", ":")) + "\n").encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def records():
    return [{"claim": claim, "state": "present-unverified"}
            for claim in REQUIRED_CLAIMS]


class CampaignCrossBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.raw_path = root / "raw.json"
        self.operators_path = root / "operators.json"
        cases = []
        for i, claim in enumerate(REQUIRED_CLAIMS):
            pos = root / f"positive-{i}.bin"
            neg = root / f"negative-{i}.bin"
            pos.write_bytes(f"positive:{claim}".encode())
            neg.write_bytes(f"negative:{claim}".encode())
            cases.append({
                "claim": claim, "positivePath": str(pos),
                "negativePath": str(neg), "positiveSha256": sha(pos.read_bytes()),
                "negativeSha256": sha(neg.read_bytes()), "issuer": "untrusted",
            })
        self.raw_document = {
            "schemaVersion": 1, "kind": "sf-pq07g-raw-evidence-intake",
            "sourceCommit": SOURCE, "sourceTree": TREE,
            "artifactSha256": ARTIFACT, "policySha256": POLICY,
            "profile": dict(PROFILE), "cases": cases,
        }
        self.operator_document = {
            "schemaVersion": 1, "kind": "sf-pq07j-external-decision-inventory",
            "sourceCommit": SOURCE, "sourceTree": TREE,
            "artifactSha256": ARTIFACT, "profile": dict(PROFILE),
            "decisions": [{
                "decisionId": key, "custodianLabel": "notAuthenticated",
                "evidenceLocationId": "notAuthenticated",
                "state": "proposed",
            } for key in REQUIRED_DECISIONS],
        }

    def reports(self):
        a = canonical(self.raw_document)
        self.raw_path.write_bytes(a)
        b = canonical(self.operator_document)
        self.operators_path.write_bytes(b)
        raw_report = inspect_campaign(
            self.raw_path, expected_manifest_sha256=sha(a),
            expected_source_commit=SOURCE, expected_source_tree=TREE,
            expected_artifact_sha256=ARTIFACT, expected_policy_sha256=POLICY,
        )
        declarations = inspect_external_decisions(
            self.operators_path, expected_manifest_sha256=sha(b),
            expected_source_commit=SOURCE, expected_source_tree=TREE,
            expected_artifact_sha256=ARTIFACT,
        )
        return raw_report, declarations

    def preflight(self, raw):
        dossier = {
            "schemaVersion": 1, "kind": "sf-pq07a-dossier-gap-report",
            "candidate": {"sourceCommit": SOURCE, "sourceTree": TREE,
                          "artifactSha256": ARTIFACT, "releaseId": "release1"},
            "scopeSupportedForReference": True, "claimStates": records(),
            "accepted": False, "productionQualified": False,
            "externalIssuerAuthenticityVerified": False,
            "providerAndTargetEvidenceIndependentlyVerified": False,
        }
        policy = {
            "schemaVersion": 1, "kind": "sf-pq07b-policy-scope-observation",
            "policySha256": POLICY, "sourceScopeMatched": True,
            "accepted": False, "productionQualified": False,
            "releaseAuthorized": False, "externalClaimsVerified": False,
            "independentPolicyCustodyVerified": False,
        }
        audit = {
            "schemaVersion": 1, "kind": "sf-pq07d-retained-byte-audit",
            "artifactSha256": ARTIFACT, "bytesRechecked": True,
            "accepted": False, "productionQualified": False,
            "releaseQualified": False, "signedProvenanceVerified": False,
            "independentPublisherCustodyVerified": False,
        }
        registry = {
            "schemaVersion": 1, "kind": "sf-pq07e-local-evidence-coverage",
            "sourceCommit": SOURCE, "artifactSha256": ARTIFACT,
            "claimStates": records(), "accepted": False,
            "productionQualified": False, "producerAuthenticityVerified": False,
            "independentAnchorVerified": False,
        }
        recovery = {
            "schemaVersion": 1, "kind": "sf-pq07c-recovery-assessment",
            "localClassification": "REFERENCE_EFFECT_PRESENT_UNVERIFIED",
            "retryAuthorized": False, "productionQualified": False,
            "targetReceiptAuthenticated": False, "remoteFenceQualified": False,
        }
        return assess_preflight(
            dossier, policy, audit, registry, recovery,
            expected_source_commit=SOURCE, expected_source_tree=TREE,
            expected_artifact_sha256=ARTIFACT, expected_policy_sha256=POLICY,
            raw_campaign=raw,
        )

    def test_full_raw_case_and_full_owner_declarations_remain_blocked(self):
        raw, owners = self.reports()
        result = self.preflight(raw)
        self.assertTrue(raw["rawCasesPresent"])
        self.assertTrue(owners["allDecisionsDeclared"])
        self.assertTrue(result["rawCampaignCasesPresent"])
        for state in (raw, owners, result):
            self.assertIs(state["productionQualified"], False)
            self.assertIs(state["publishAuthorized"], False)
            self.assertIs(state["adopterPilotAuthorized"], False)
        self.assertFalse(owners["custodyAuthenticated"])
        self.assertEqual(result["SF_R10"], "UNMET-overall")

    def test_changed_cross_package_artifact_is_rejected(self):
        raw, _ = self.reports()
        raw["artifactSha256"] = "1" * 64
        with self.assertRaises(PreflightError):
            self.preflight(raw)

    def test_declared_owner_cannot_self_approve_live_campaign(self):
        self.operator_document["decisions"][0]["state"] = "approved"
        with self.assertRaises(ExternalReadinessError):
            self.reports()


if __name__ == "__main__":
    unittest.main()
