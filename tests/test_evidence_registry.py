"""PQ-07E local evidence byte and hash-chain preservation tests."""
import sqlite3
from contextlib import closing
import tempfile
import unittest
from pathlib import Path

from sf.evidence_registry import EvidenceRegistry, EvidenceRegistryError
from sf.production_dossier import REQUIRED_CLAIMS

SHA = "a" * 40
ART = "b" * 64


class EvidenceRegistryTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "evidence.db"

    def put(self, db, eid="event1", claim=None, kind="positive",
            raw=b"fixture bytes", source=SHA):
        return db.append(eid, claim or REQUIRED_CLAIMS[0],
                         kind, "case1", source, ART, raw)

    def test_restart_replay_and_conflicting_reuse(self):
        with EvidenceRegistry(self.path) as db:
            self.assertEqual(self.put(db)["status"], "recorded-locally")
            self.assertEqual(self.put(db)["status"], "already-recorded")
            with self.assertRaises(EvidenceRegistryError):
                self.put(db, raw=b"altered bytes")
        with EvidenceRegistry(self.path) as db:
            self.assertEqual(db.verify_chain()["total"], 1)
            self.assertEqual(db.coverage(SHA, ART)["claimStates"][0]["state"], "missing")

    def test_all_reference_positive_negative_cases_still_unqualified(self):
        with EvidenceRegistry(self.path) as db:
            for i, claim in enumerate(REQUIRED_CLAIMS):
                self.put(db, f"positive{i}", claim, "positive")
                self.put(db, f"negative{i}", claim, "negative")
            report = db.coverage(SHA, ART)
            self.assertTrue(all(r["state"] == "present-unverified"
                                for r in report["claimStates"]))
            self.assertFalse(report["producerAuthenticityVerified"])
            self.assertFalse(report["accepted"])
            self.assertFalse(report["productionQualified"])
            self.assertTrue(all(r["state"] == "missing"
                                for r in db.coverage("c" * 40, ART)["claimStates"]))

    def test_modified_raw_payload_detected(self):
        with EvidenceRegistry(self.path) as db:
            self.put(db)
        with closing(sqlite3.connect(self.path)) as raw:
            raw.execute("UPDATE events SET body=? WHERE event_id='event1'", (b"tampered",))
            raw.commit()
        with EvidenceRegistry(self.path) as db:
            with self.assertRaises(EvidenceRegistryError):
                db.verify_chain()
            with self.assertRaises(EvidenceRegistryError):
                self.put(db, "event2")

    def test_reject_invalid_identity_and_unbounded_body(self):
        with EvidenceRegistry(self.path) as db:
            with self.assertRaises(EvidenceRegistryError):
                self.put(db, "bad/path")
            with self.assertRaises(EvidenceRegistryError):
                self.put(db, raw=b"x" * (1024 * 1024 + 1))
            with self.assertRaises(EvidenceRegistryError):
                self.put(db, claim="unrecognized")


if __name__ == "__main__":
    unittest.main()
