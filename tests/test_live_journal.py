"""PQ-06 durable journal tests, using fabricated HMAC observations only."""
import hashlib
import hmac
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from sf.live_journal import LiveJournal, JournalError, canonical


class LiveJournalTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "incident.db"
        self.key = b"example independent telemetry key for tests"
        self.operator = b"example independent operator approval key"
        self.now = datetime(2026, 10, 9, 8, 0, 0, tzinfo=timezone.utc)
        self.event = {
            "schemaVersion": 1, "eventId": "event1",
            "source": "agent1", "target": "service1", "environment": "test",
            "epoch": 2, "sequence": 1, "domain": "health",
            "state": "failed", "observedAt": "2026-10-09T07:59:59Z",
            "evidenceSha256": "a" * 64,
        }
        self.scope = dict(expected_source="agent1", expected_target="service1",
                          expected_environment="test", now=self.now)

    def mac(self, body, secret):
        return hmac.new(secret, canonical(body), hashlib.sha256).hexdigest()

    def observe(self, journal, event=None, **kwargs):
        value = self.event if event is None else event
        return journal.observe(value, self.mac(value, self.key), self.key,
                               **{**self.scope, **kwargs})

    def test_incident_survives_restart_and_healthy_does_not_close(self):
        with LiveJournal(self.path) as first:
            one = self.observe(first)
            self.assertTrue(one["incidentOpened"])
        with LiveJournal(self.path) as second:
            followup = {**self.event, "eventId": "event2", "sequence": 2,
                        "state": "healthy"}
            self.observe(second, followup)
            self.assertEqual(second.incident("event1")["status"], "OPEN")
            self.assertFalse(second.incident("event1")["liveOperationsQualified"])

    def test_replay_stale_and_wrong_scope_rejected(self):
        with LiveJournal(self.path) as journal:
            self.observe(journal)
            with self.assertRaises(JournalError):
                self.observe(journal)
            with self.assertRaises(JournalError):
                self.observe(journal, {**self.event, "eventId": "event2", "sequence": 1})
            with self.assertRaises(JournalError):
                self.observe(journal, {**self.event, "eventId": "event3", "sequence": 3},
                             expected_target="wrong")
            with self.assertRaises(JournalError):
                self.observe(journal, {**self.event, "eventId": "event4", "sequence": 4,
                                       "observedAt": "2026-10-09T06:00:00Z"})

    def test_forged_telemetry_rejected(self):
        with LiveJournal(self.path) as journal:
            with self.assertRaises(JournalError):
                journal.observe(self.event, "f" * 64, self.key, **self.scope)
            self.assertIsNone(journal.incident("event1"))

    def test_explicit_operator_resolution_only(self):
        with LiveJournal(self.path) as journal:
            self.observe(journal)
            with self.assertRaises(JournalError):
                journal.resolve("event1", "operator1", "b" * 64, "f" * 64, self.operator)
            decision = {"incidentId": "event1", "operatorId": "operator1",
                        "recoverySha256": "b" * 64}
            result = journal.resolve("event1", "operator1", "b" * 64,
                                     self.mac(decision, self.operator), self.operator)
            self.assertEqual(result["status"], "RESOLVED")
            with self.assertRaises(JournalError):
                journal.resolve("event1", "operator1", "b" * 64,
                                self.mac(decision, self.operator), self.operator)


if __name__ == "__main__":
    unittest.main()
