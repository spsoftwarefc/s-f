"""PQ-07G raw evidence is inventory, never independently authenticated proof."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from sf.campaign_intake import CampaignIntakeError, inspect_campaign
from sf.production_dossier import REQUIRED_CLAIMS


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def encoded(obj: dict) -> bytes:
    return (json.dumps(obj, sort_keys=True, ensure_ascii=True,
                       allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")


class CampaignIntakeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = self.root / "operator-intake.json"
        self.case_files = []
        cases = []
        for i, claim in enumerate(REQUIRED_CLAIMS):
            pos = self.root / f"positive-{i}.bin"
            neg = self.root / f"negative-{i}.bin"
            pos.write_bytes(f"positive:{claim}".encode("ascii"))
            neg.write_bytes(f"negative:{claim}".encode("ascii"))
            self.case_files.append((pos, neg))
            cases.append({
                "claim": claim, "positivePath": str(pos),
                "positiveSha256": digest(pos.read_bytes()),
                "negativePath": str(neg), "negativeSha256": digest(neg.read_bytes()),
                "issuer": "untrustedClaimant",
            })
        self.document = {
            "schemaVersion": 1, "kind": "sf-pq07g-raw-evidence-intake",
            "sourceCommit": "a" * 40, "sourceTree": "b" * 40,
            "artifactSha256": "c" * 64, "policySha256": "d" * 64,
            "profile": {"scopeId": "reference1", "platform": "linux",
                        "adapter": "disposable-single-host", "environment": "test"},
            "cases": cases,
        }

    def call(self):
        raw = encoded(self.document)
        self.manifest.write_bytes(raw)
        return inspect_campaign(
            self.manifest, expected_manifest_sha256=digest(raw),
            expected_source_commit="a" * 40, expected_source_tree="b" * 40,
            expected_artifact_sha256="c" * 64, expected_policy_sha256="d" * 64,
        )

    def test_complete_raw_bytes_remain_untrusted(self):
        out = self.call()
        self.assertTrue(out["rawCasesPresent"])
        self.assertEqual(len(out["claimCases"]), len(REQUIRED_CLAIMS))
        self.assertEqual(out["status"], "BLOCKED-external-qualification")
        for field in ("externalEvidenceAuthenticated", "candidateIssuerLabelsAuthenticated",
                      "independentPolicyCustodyVerified", "releaseAuthorized",
                      "publishAuthorized", "adopterPilotAuthorized", "productionQualified"):
            self.assertIs(out[field], False)

    def test_missing_positive_and_negative_are_not_quietly_green(self):
        self.case_files[0][0].unlink()
        self.case_files[1][1].unlink()
        out = self.call()
        self.assertFalse(out["rawCasesPresent"])
        self.assertEqual(out["claimCases"][0]["positive"], "missing")
        self.assertEqual(out["claimCases"][1]["negative"], "missing")

    def test_changed_or_alias_raw_evidence_fails_closed(self):
        self.case_files[0][0].write_bytes(b"substituted")
        with self.assertRaises(CampaignIntakeError):
            self.call()
        self.case_files[0][0].write_bytes(b"positive:" + REQUIRED_CLAIMS[0].encode())
        self.document["cases"][0]["negativePath"] = self.document["cases"][0]["positivePath"]
        with self.assertRaises(CampaignIntakeError):
            self.call()

    def test_duplicate_claim_and_same_expected_proof_rejected(self):
        self.document["cases"][1] = dict(self.document["cases"][0])
        with self.assertRaises(CampaignIntakeError):
            self.call()
        self.document["cases"][1] = {
            **self.document["cases"][1],
            "claim": REQUIRED_CLAIMS[1],
            "negativeSha256": self.document["cases"][1]["positiveSha256"],
        }
        with self.assertRaises(CampaignIntakeError):
            self.call()

    def test_wrong_scope_policy_or_candidate_rejected(self):
        self.document["policySha256"] = "e" * 64
        with self.assertRaises(CampaignIntakeError):
            self.call()
        self.document["policySha256"] = "d" * 64
        self.document["profile"]["platform"] = "windows"
        with self.assertRaises(CampaignIntakeError):
            self.call()
        self.document["profile"]["platform"] = "linux"
        self.document["sourceTree"] = "0" * 40
        with self.assertRaises(CampaignIntakeError):
            self.call()

    def test_no_extra_claim_of_external_authority(self):
        self.document["productionQualified"] = True
        with self.assertRaises(CampaignIntakeError):
            self.call()

    def test_noncanonical_duplicate_or_wrong_manifest_pin(self):
        raw = encoded(self.document)
        self.manifest.write_bytes(raw + b" ")
        with self.assertRaises(CampaignIntakeError):
            inspect_campaign(
                self.manifest, expected_manifest_sha256=digest(raw),
                expected_source_commit="a" * 40, expected_source_tree="b" * 40,
                expected_artifact_sha256="c" * 64, expected_policy_sha256="d" * 64,
            )
        self.document["cases"] = []
        raw = encoded(self.document)
        duplicate = raw.replace(b'"schemaVersion":1,', b'"schemaVersion":1,"schemaVersion":1,')
        self.manifest.write_bytes(duplicate)
        with self.assertRaises(CampaignIntakeError):
            inspect_campaign(
                self.manifest, expected_manifest_sha256=digest(duplicate),
                expected_source_commit="a" * 40, expected_source_tree="b" * 40,
                expected_artifact_sha256="c" * 64, expected_policy_sha256="d" * 64,
            )

    def test_symlinked_case_denied_when_supported(self):
        pointer = self.root / "link"
        try:
            pointer.symlink_to(self.case_files[0][0])
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable on this platform")
        self.document["cases"][0]["positivePath"] = str(pointer)
        with self.assertRaises(CampaignIntakeError):
            self.call()


if __name__ == "__main__":
    unittest.main()
