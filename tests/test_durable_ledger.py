"""PQ-04 durable ledger tests use real SQLite files and connections."""
import tempfile
import unittest
from pathlib import Path

from sf.durable_ledger import DurableLedger, LedgerError


class DurableTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "ledger.db"

    def test_immutable_intent_survives_close(self):
        with DurableLedger(self.path) as ledger:
            row = ledger.prepare("op1", "a" * 64)
            self.assertEqual(row["state"], "PREPARED")
            ledger.prepare("op1", "a" * 64)
            with self.assertRaises(LedgerError):
                ledger.prepare("op1", "b" * 64)
        with DurableLedger(self.path) as second:
            self.assertEqual(second.get("op1")["intentSha256"], "a" * 64)

    def test_unknown_crash_state_blocks_reissue_and_stale_fence(self):
        with DurableLedger(self.path) as first:
            first.prepare("op1", "a" * 64)
            fence = first.reserve("op1", "a" * 64, minimum_generation=4)
            self.assertEqual(fence["generation"], 5)
            first.possible_send("op1", 5)
        with DurableLedger(self.path) as restarted:
            self.assertEqual(restarted.get("op1")["state"], "UNKNOWN")
            with self.assertRaises(LedgerError):
                restarted.reserve("op1", "a" * 64)
            with self.assertRaises(LedgerError):
                restarted.possible_send("op1", 4)
            self.assertEqual(restarted.hold_for_reconciliation("op1", 5)["state"], "BLOCKED")

    def test_second_process_connection_does_not_duplicate_dispatch(self):
        with DurableLedger(self.path) as first, DurableLedger(self.path) as second:
            first.prepare("op1", "a" * 64)
            first.reserve("op1", "a" * 64)
            with self.assertRaises(LedgerError):
                second.reserve("op1", "a" * 64)

    def test_missing_or_bad_intent_denied(self):
        with DurableLedger(self.path) as ledger:
            with self.assertRaises(LedgerError):
                ledger.reserve("missing", "a" * 64)
            with self.assertRaises(LedgerError):
                ledger.prepare("../escape", "a" * 64)
            with self.assertRaises(LedgerError):
                ledger.prepare("op", "x" * 64)

    def test_generation_cannot_overflow(self):
        with DurableLedger(self.path) as ledger:
            ledger.prepare("op", "a" * 64)
            with self.assertRaises(LedgerError):
                ledger.reserve("op", "a" * 64, minimum_generation=2**63 - 1)


if __name__ == "__main__":
    unittest.main()
