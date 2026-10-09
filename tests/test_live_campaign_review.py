"""PQ-07W full source oracle still rejects live authority and incident closure."""
import unittest

from sf.production_dossier import REQUIRED_CLAIMS
from sf.live_campaign_review import LiveCampaignReviewError, review_live_campaign


class LiveCampaignReviewTests(unittest.TestCase):
    def setUp(self):
        self.intake = {"kind": "sf-pq07t-live-campaign-intake-no-go",
                       "sourceCommit": "a" * 40, "artifactSha256": "c" * 64,
                       "policySha256": "d" * 64, "productionQualified": False,
                       "accepted": False}
        self.supply = {"kind": "sf-pq07u-supply-chain-handoff-no-go",
                       "sourceCommit": "a" * 40, "artifactSha256": "c" * 64,
                       "policySha256": "d" * 64, "readOnlyObservationsConsistent": True,
                       "effectGrantVerified": False, "releaseAuthorized": False,
                       "deploymentAuthorized": False, "productionQualified": False,
                       "accepted": False}
        self.target = {"kind": "sf-pq07v-reference-target-no-go",
                       "sourceCommit": "a" * 40, "artifactSha256": "c" * 64,
                       "targetId": "disposable01", "capabilitiesDeclared": True,
                       "actualTargetOwnershipAuthenticated": False,
                       "destinationCASVerified": False, "remoteReceiptAuthenticated": False,
                       "liveFaultCasesExecuted": False, "liveRecoveryQualified": False,
                       "externalEffectAuthorized": False,
                       "productionQualified": False, "accepted": False}
        self.recovery = {"kind": "sf-pq07q-local-reference-process-death",
                         "localProcessExitObserved": True, "localReceiptRecovered": True,
                         "realRemoteFenceQualified": False, "realServiceDeployed": False,
                         "liveOperationsVerified": False, "productionQualified": False}
        self.ops = {"schemaVersion": 1, "kind": "sf-pq07w-operator-incident-intake",
                    "sourceCommit": "a" * 40, "targetId": "disposable01",
                    "observerIdentityDeclared": True, "openIncidents": ["incA"],
                    "verifiedLiveTelemetry": False, "incidentOwnerAuthenticated": False,
                    "operationsQualified": False, "accepted": False}
        self.cases = [{"claim": claim, "positive": "present-unverified",
                       "negative": "present-unverified"}
                      for claim in REQUIRED_CLAIMS]

    def review(self):
        return review_live_campaign(
            self.intake, self.supply, self.target, self.recovery,
            self.ops, self.cases, expected_source_commit="a" * 40,
        )

    def test_complete_local_records_preserve_no_go_and_incidents(self):
        result = self.review()
        self.assertTrue(result["claimCasesPresentUnverified"])
        self.assertEqual(result["unresolvedIncidentCount"], 1)
        self.assertEqual(result["SF_R10"], "UNMET-overall")
        for key in ("independentlyAuthenticatedOperations",
                    "independentlyQualifiedPublisher", "independentlyQualifiedDeployment",
                    "releaseAuthorized", "publishAuthorized", "productionQualified",
                    "adopterPilotAuthorized", "accepted"):
            self.assertFalse(result[key])

    def test_wrong_source_and_artifact_fail(self):
        for record, key, bad in ((self.intake, "sourceCommit", "0" * 40),
                                 (self.target, "artifactSha256", "e" * 64),
                                 (self.supply, "policySha256", "f" * 64),
                                 (self.ops, "targetId", "otherTarget")):
            previous = record[key]
            record[key] = bad
            with self.assertRaises(LiveCampaignReviewError):
                self.review()
            record[key] = previous

    def test_false_authority_is_rejected(self):
        for record, key in ((self.intake, "productionQualified"),
                            (self.supply, "effectGrantVerified"),
                            (self.target, "destinationCASVerified"),
                            (self.recovery, "realServiceDeployed"),
                            (self.ops, "verifiedLiveTelemetry"),
                            (self.ops, "incidentOwnerAuthenticated")):
            record[key] = True
            with self.assertRaises(LiveCampaignReviewError):
                self.review()
            record[key] = False

    def test_approval_or_missing_negative_proof_does_not_qualify(self):
        self.cases[0]["negative"] = "approved"
        with self.assertRaises(LiveCampaignReviewError):
            self.review()
        self.cases[0]["negative"] = "missing"
        self.assertFalse(self.review()["claimCasesPresentUnverified"])
        self.cases.pop()
        with self.assertRaises(LiveCampaignReviewError):
            self.review()

    def test_incident_replay_and_candidate_closed_field_fail(self):
        self.ops["openIncidents"] = ["incA", "incA"]
        with self.assertRaises(LiveCampaignReviewError):
            self.review()
        self.ops["openIncidents"] = ["incA"]
        self.ops["incidentResolved"] = True
        with self.assertRaises(LiveCampaignReviewError):
            self.review()


if __name__ == "__main__":
    unittest.main()
