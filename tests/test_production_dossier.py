"""PQ-07A: source-bound dossier gaps cannot self-certify production."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sf.production_dossier import DossierError, assess_dossier, read_dossier, REQUIRED_CLAIMS


def sample():
    return {
        "schemaVersion": 1, "kind": "sf-pq07a-source-dossier",
        "candidate": {"sourceCommit": "a" * 40, "sourceTree": "b" * 40,
                      "artifactSha256": "c" * 64, "releaseId": "v1"},
        "profile": {"scopeId": "reference1", "platform": "linux",
                    "adapter": "disposable-single-host", "environment": "test"},
        "evidence": [], "excludedCapabilities": ["SF-18-shared-budget"],
    }


def evidence(claim):
    return {"claim": claim, "sourceCommit": "a" * 40,
            "sourceTree": "b" * 40, "artifactSha256": "c" * 64,
            "evidenceSha256": "d" * 64, "negativeCaseSha256": "e" * 64,
            "issuer": "untrustedCandidate", "disposition": "observed"}


class DossierTests(unittest.TestCase):
    def test_missing_claims_are_explicit(self):
        value = assess_dossier(sample())
        self.assertEqual(len(value["claimStates"]), len(REQUIRED_CLAIMS))
        self.assertTrue(all(x["state"] == "missing" for x in value["claimStates"]))
        self.assertFalse(value["accepted"])
        self.assertFalse(value["productionQualified"])
        self.assertEqual(value["SF_R10"], "UNMET-overall")

    def test_all_candidate_labels_present_is_never_authority(self):
        d = sample()
        d["evidence"] = [evidence(name) for name in REQUIRED_CLAIMS]
        result = assess_dossier(d)
        self.assertTrue(all(x["state"] == "present-unverified" for x in result["claimStates"]))
        self.assertFalse(result["externalIssuerAuthenticityVerified"])
        self.assertFalse(result["providerAndTargetEvidenceIndependentlyVerified"])
        self.assertFalse(result["productionQualified"])

    def test_wrong_source_artifact_is_rejected(self):
        d = sample()
        d["evidence"] = [{**evidence(REQUIRED_CLAIMS[0]), "artifactSha256": "0" * 64}]
        self.assertEqual(assess_dossier(d)["claimStates"][0]["state"], "identity-rejected")

    def test_unsupported_profile_rejects_all_claims(self):
        d = sample()
        d["profile"]["environment"] = "production"
        d["evidence"] = [evidence(REQUIRED_CLAIMS[0])]
        result = assess_dossier(d)
        self.assertTrue(all(x["state"] == "unsupported-profile" for x in result["claimStates"]))
        self.assertFalse(result["productionQualified"])

    def test_unknown_duplicates_or_forged_verification_are_denied(self):
        d = sample()
        d["evidence"] = [evidence(REQUIRED_CLAIMS[0]), evidence(REQUIRED_CLAIMS[0])]
        with self.assertRaises(DossierError):
            assess_dossier(d)
        d["evidence"] = [{**evidence(REQUIRED_CLAIMS[0]), "disposition": "authenticated"}]
        with self.assertRaises(DossierError):
            assess_dossier(d)
        d["evidence"] = [{**evidence(REQUIRED_CLAIMS[0]), "trusted": True}]
        with self.assertRaises(DossierError):
            assess_dossier(d)

    def test_file_reader_rejects_duplicate_json_members(self):
        with tempfile.TemporaryDirectory() as temp:
            f = Path(temp) / "dossier.json"
            f.write_text('{"schemaVersion":1,"schemaVersion":1}')
            with self.assertRaises(DossierError):
                read_dossier(f)
            f.write_text(json.dumps(sample()))
            self.assertEqual(assess_dossier(read_dossier(f))["status"], "not-qualified")

    def test_illegal_exclusions_denied_and_r10_stays_unmet(self):
        d = sample()
        d["excludedCapabilities"] = ["SF-R10"]
        with self.assertRaises(DossierError):
            assess_dossier(d)
        d["excludedCapabilities"] = ["SF-17-agent-host", "SF-18-shared-budget"]
        self.assertEqual(assess_dossier(d)["SF_R10"], "UNMET-overall")


if __name__ == "__main__":
    unittest.main()
