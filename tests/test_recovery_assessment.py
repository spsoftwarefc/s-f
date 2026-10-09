"""Actual abruptly terminated subprocess and SQLite reopening campaign.

os._exit tests process death only, NOT host/power-loss durability guarantees.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from sf.durable_ledger import DurableLedger, LedgerError
from sf.reference_target import ReferenceTarget
from sf.recovery_assessment import assess_local_recovery, RecoveryAssessmentError

INTENT = "a" * 64
ARTIFACT = "b" * 64


class ProcessDeathCampaignTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.ledger = self.root / "intent.db"
        self.target = self.root / "target.db"
        with DurableLedger(self.ledger), ReferenceTarget(self.target):
            pass

    def die_child(self, phase):
        # The child itself has no credentials or network access.
        script = (
            "import os,sys\n"
            "from pathlib import Path\n"
            "from sf.durable_ledger import DurableLedger\n"
            "from sf.reference_target import ReferenceTarget\n"
            "ledger=Path(sys.argv[1]); target=Path(sys.argv[2]); phase=sys.argv[3]\n"
            "with DurableLedger(ledger) as db:\n"
            " db.prepare('operation1', 'a'*64)\n"
            " if phase=='intent': os._exit(73)\n"
            " generation=db.reserve('operation1','a'*64)['generation']\n"
            " if phase=='reserved': os._exit(73)\n"
            " db.possible_send('operation1',generation)\n"
            " if phase=='possible-send': os._exit(73)\n"
            " with ReferenceTarget(target) as store:\n"
            "  store.apply('operation1',generation,'b'*64,None)\n"
            " os._exit(73)\n"
        )
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
        completed = subprocess.run(
            [sys.executable, "-c", script, str(self.ledger), str(self.target), phase],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, timeout=15,
            check=False)
        self.assertEqual(completed.returncode, 73, completed.stderr.decode(errors="replace"))

    def assess(self):
        return assess_local_recovery(self.ledger, self.target,
                                     "operation1", INTENT, ARTIFACT)

    def test_pre_dispatch_intent_survives_process_death(self):
        self.die_child("intent")
        result = self.assess()
        self.assertEqual(result["localClassification"], "INTENT_ONLY")
        self.assertFalse(result["retryAuthorized"])

    def test_reservation_survives_process_death(self):
        self.die_child("reserved")
        self.assertEqual(self.assess()["localClassification"], "UNKNOWN_EFFECT")
        with DurableLedger(self.ledger) as db:
            with self.assertRaises(LedgerError):
                db.reserve("operation1", INTENT)

    def test_lost_dispatch_reply_remains_unknown_without_target(self):
        self.die_child("possible-send")
        result = self.assess()
        self.assertEqual(result["intentState"], "UNKNOWN")
        self.assertEqual(result["localClassification"], "UNKNOWN_EFFECT")
        self.assertFalse(result["targetReceiptAuthenticated"])
        with DurableLedger(self.ledger) as db:
            with self.assertRaises(LedgerError):
                db.reserve("operation1", INTENT)

    def test_effect_before_crash_is_idempotently_recorded_but_untrusted(self):
        self.die_child("after-effect")
        result = self.assess()
        self.assertEqual(result["localClassification"],
                         "REFERENCE_EFFECT_PRESENT_UNVERIFIED")
        self.assertTrue(result["manualReconciliationRequired"])
        with ReferenceTarget(self.target) as db:
            receipt = db.apply("operation1", 1, ARTIFACT, None)
            self.assertEqual(receipt["state"], "APPLIED")
            self.assertEqual(db.snapshot()["generation"], 1)

    def test_mismatched_expected_artifact_and_intent_denied(self):
        self.die_child("after-effect")
        result = assess_local_recovery(self.ledger,self.target,
                                       "operation1",INTENT,"c"*64)
        self.assertEqual(result["localClassification"], "CONTRADICTORY")
        with self.assertRaises(RecoveryAssessmentError):
            assess_local_recovery(self.ledger,self.target,
                                  "operation1","d"*64,ARTIFACT)


if __name__ == "__main__":
    unittest.main()
