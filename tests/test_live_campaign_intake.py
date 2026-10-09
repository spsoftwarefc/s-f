"""PQ-07T manifest intake must reject synthetic authorization and stale scope."""
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from sf.external_readiness import REQUIRED_DECISIONS
from sf.live_campaign_intake import LiveCampaignIntakeError, inspect_live_campaign

CLOCK = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True, allow_nan=False) + "\n").encode()


class LiveCampaignIntakeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "campaign.json"
        self.doc = {
            "schemaVersion": 1, "kind": "sf-pq07t-live-campaign-intake",
            "sourceCommit": "a" * 40, "sourceTree": "b" * 40,
            "artifactSha256": "c" * 64, "policySha256": "d" * 64,
            "profile": {"scopeId": "ref", "platform": "linux",
                        "adapter": "disposable-single-host", "environment": "test"},
            "preparedAt": "2026-10-09T11:00:00Z",
            "expiresAt": "2026-10-09T13:00:00Z",
            "externalDecisions": [],
        }

    def check(self, *, pin=None):
        raw = canonical(self.doc)
        self.path.write_bytes(raw)
        return inspect_live_campaign(
            self.path, expected_manifest_sha256=pin or hashlib.sha256(raw).hexdigest(),
            expected_source_commit="a" * 40, expected_source_tree="b" * 40,
            expected_artifact_sha256="c" * 64,
            expected_policy_sha256="d" * 64, now=CLOCK,
        )

    def test_valid_candidate_is_never_live_authorized(self):
        result = self.check()
        self.assertEqual(len(result["missingDecisionIds"]), len(REQUIRED_DECISIONS))
        for field in ("independentCustodyVerified", "providerAuthenticated",
                      "releaseAuthorized", "deploymentAuthorized", "publishAuthorized",
                      "productionQualified", "accepted"):
            self.assertIs(result[field], False)

    def test_all_declarations_are_not_approval(self):
        self.doc["externalDecisions"] = [
            {"decisionId": key, "referenceSha256": "e" * 64, "state": "pending"}
            for key in REQUIRED_DECISIONS
        ]
        result = self.check()
        self.assertTrue(result["allDecisionsDeclared"])
        self.assertFalse(result["productionQualified"])

    def test_wrong_pin_and_scope_fail(self):
        with self.assertRaises(LiveCampaignIntakeError):
            self.check(pin="0" * 64)
        for field, value in (("sourceCommit", "0" * 40),
                             ("artifactSha256", "0" * 64),
                             ("policySha256", "0" * 64)):
            with self.subTest(field=field):
                old = self.doc[field]
                self.doc[field] = value
                with self.assertRaises(LiveCampaignIntakeError):
                    self.check()
                self.doc[field] = old

    def test_expiry_future_and_wrong_profile_fail(self):
        for field, value in (("preparedAt", "2026-10-09T13:00:00Z"),
                             ("expiresAt", "2026-10-09T10:00:00Z"),
                             ("expiresAt", "2026-10-11T13:00:00Z")):
            with self.subTest(field=field, value=value):
                old = self.doc[field]
                self.doc[field] = value
                with self.assertRaises(LiveCampaignIntakeError):
                    self.check()
                self.doc[field] = old
        self.doc["profile"]["environment"] = "production"
        with self.assertRaises(LiveCampaignIntakeError):
            self.check()

    def test_forged_approval_duplicates_and_extra_fields_fail(self):
        row = {"decisionId": REQUIRED_DECISIONS[0],
               "referenceSha256": "e" * 64, "state": "pending"}
        for items in ([{**row, "state": "approved"}], [row, row],
                      [{**row, "accepted": True}]):
            self.doc["externalDecisions"] = items
            with self.assertRaises(LiveCampaignIntakeError):
                self.check()
        self.doc["externalDecisions"] = []
        self.doc["productionQualified"] = True
        with self.assertRaises(LiveCampaignIntakeError):
            self.check()

    def test_duplicate_json_key_rejected(self):
        raw = canonical(self.doc).replace(b'"schemaVersion":1,',
                                           b'"schemaVersion":1,"schemaVersion":1,')
        self.path.write_bytes(raw)
        with self.assertRaises(LiveCampaignIntakeError):
            inspect_live_campaign(
                self.path, expected_manifest_sha256=hashlib.sha256(raw).hexdigest(),
                expected_source_commit="a" * 40, expected_source_tree="b" * 40,
                expected_artifact_sha256="c" * 64,
                expected_policy_sha256="d" * 64, now=CLOCK,
            )


if __name__ == "__main__":
    unittest.main()
