"""PQ-07I subprocess CLI verification: success is always a local NO-GO."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "pq07_campaign.py"


def canonical(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True,
                       allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")


class CampaignCLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "manifest.json"
        self.data = {
            "schemaVersion": 1, "kind": "sf-pq07g-raw-evidence-intake",
            "sourceCommit": "a" * 40, "sourceTree": "b" * 40,
            "artifactSha256": "c" * 64, "policySha256": "d" * 64,
            "profile": {"scopeId": "reference", "platform": "linux",
                        "adapter": "disposable-single-host", "environment": "test"},
            "cases": [],
        }

    def run_cli(self, *, bad_pin=False):
        raw = canonical(self.data)
        self.path.write_bytes(raw)
        return subprocess.run([
            sys.executable, str(SCRIPT), "--manifest", str(self.path),
            "--manifest-sha256", ("0" * 64 if bad_pin else hashlib.sha256(raw).hexdigest()),
            "--source-commit", "a" * 40, "--source-tree", "b" * 40,
            "--artifact-sha256", "c" * 64, "--policy-sha256", "d" * 64,
        ], text=True, capture_output=True, timeout=15, check=False)

    def test_valid_raw_intake_is_machine_readable_but_not_qualified(self):
        process = self.run_cli()
        self.assertEqual(process.returncode, 0, process.stderr)
        report = json.loads(process.stdout)
        self.assertEqual(report["status"], "BLOCKED-external-qualification")
        self.assertFalse(report["rawCasesPresent"])
        self.assertFalse(report["productionQualified"])
        self.assertFalse(report["releaseAuthorized"])
        self.assertFalse(report["adopterPilotAuthorized"])

    def test_wrong_pin_is_error_not_accepted(self):
        process = self.run_cli(bad_pin=True)
        self.assertEqual(process.returncode, 2)
        self.assertEqual(process.stdout, "")
        self.assertIn("rejected", process.stderr)

    def test_unqualified_scope_cannot_be_promoted(self):
        self.data["profile"]["environment"] = "production"
        process = self.run_cli()
        self.assertEqual(process.returncode, 2)
        self.assertEqual(process.stdout, "")

    def test_candidate_claiming_production_authority_is_rejected(self):
        self.data["productionQualified"] = True
        process = self.run_cli()
        self.assertEqual(process.returncode, 2)
        self.assertEqual(process.stdout, "")


if __name__ == "__main__":
    unittest.main()
