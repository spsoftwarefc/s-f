"""PQ-07J: operator declarations never authenticate their own owners."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from sf.external_readiness import (
    ExternalReadinessError, REQUIRED_DECISIONS, inspect_external_decisions,
)


def canonical(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=True,
                       allow_nan=False, separators=(",", ":")) + "\n").encode()


class ExternalReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "decisions.json"
        self.manifest = {
            "schemaVersion": 1, "kind": "sf-pq07j-external-decision-inventory",
            "sourceCommit": "a" * 40, "sourceTree": "b" * 40,
            "artifactSha256": "c" * 64,
            "profile": {"scopeId": "reference", "platform": "linux",
                        "adapter": "disposable-single-host", "environment": "test"},
            "decisions": [],
        }

    def run_check(self):
        raw = canonical(self.manifest)
        self.path.write_bytes(raw)
        return inspect_external_decisions(
            self.path, expected_manifest_sha256=hashlib.sha256(raw).hexdigest(),
            expected_source_commit="a" * 40, expected_source_tree="b" * 40,
            expected_artifact_sha256="c" * 64,
        )

    def test_absent_external_decisions_report_missing(self):
        output = self.run_check()
        self.assertFalse(output["allDecisionsDeclared"])
        self.assertEqual(len(output["decisionStates"]), len(REQUIRED_DECISIONS))
        self.assertTrue(all(r["state"] == "missing" for r in output["decisionStates"]))
        self.assertFalse(output["custodyAuthenticated"])
        self.assertFalse(output["productionQualified"])

    def test_every_declared_custodian_still_has_no_proof_of_authority(self):
        self.manifest["decisions"] = [
            {"decisionId": key, "custodianLabel": "sourceLabel",
             "evidenceLocationId": "localStore", "state": "proposed"}
            for key in REQUIRED_DECISIONS
        ]
        output = self.run_check()
        self.assertTrue(output["allDecisionsDeclared"])
        for label in ("custodyAuthenticated", "externalEffectsAuthorized",
                      "productionQualified", "publishAuthorized", "adopterPilotAuthorized"):
            self.assertFalse(output[label])

    def test_source_candidate_and_platform_mismatch_rejected(self):
        self.manifest["sourceCommit"] = "e" * 40
        with self.assertRaises(ExternalReadinessError):
            self.run_check()
        self.manifest["sourceCommit"] = "a" * 40
        self.manifest["profile"]["adapter"] = "production-vps"
        with self.assertRaises(ExternalReadinessError):
            self.run_check()

    def test_duplicate_or_fabricated_approval_rejected(self):
        row = {"decisionId": REQUIRED_DECISIONS[0], "custodianLabel": "actor",
               "evidenceLocationId": "custody", "state": "proposed"}
        self.manifest["decisions"] = [row, dict(row)]
        with self.assertRaises(ExternalReadinessError):
            self.run_check()
        self.manifest["decisions"] = [{**row, "state": "approved"}]
        with self.assertRaises(ExternalReadinessError):
            self.run_check()
        self.manifest["decisions"] = [row]
        self.manifest["productionQualified"] = True
        with self.assertRaises(ExternalReadinessError):
            self.run_check()

    def test_wrong_manifest_digest_rejected(self):
        raw = canonical(self.manifest)
        self.path.write_bytes(raw)
        with self.assertRaises(ExternalReadinessError):
            inspect_external_decisions(
                self.path, expected_manifest_sha256="0" * 64,
                expected_source_commit="a" * 40, expected_source_tree="b" * 40,
                expected_artifact_sha256="c" * 64,
            )


if __name__ == "__main__":
    unittest.main()
