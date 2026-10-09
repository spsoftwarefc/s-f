"""PQ-07U across existing source-only publisher and provider observations."""
import copy
import unittest

from sf.supply_chain_handoff import (
    SupplyChainHandoffError, assess_supply_chain_handoff,
)


class SupplyChainHandoffTests(unittest.TestCase):
    def setUp(self):
        self.intake = {
            "kind": "sf-pq07t-live-campaign-intake-no-go",
            "sourceCommit": "a" * 40, "sourceTree": "b" * 40,
            "artifactSha256": "c" * 64, "policySha256": "d" * 64,
            "status": "BLOCKED-external-qualification",
            "independentCustodyVerified": False, "providerAuthenticated": False,
            "releaseAuthorized": False, "deploymentAuthorized": False,
            "publishAuthorized": False, "adopterPilotAuthorized": False,
            "productionQualified": False, "accepted": False,
        }
        self.retained = {
            "kind": "sf-pq07p-retained-publisher-no-go",
            "sourceCommit": "a" * 40, "sourceTree": "b" * 40,
            "artifactSha256": "c" * 64, "policySha256": "d" * 64,
            "exactRetainedBytesObserved": True,
            "independentRetentionCustodyVerified": False,
            "independentPolicyCustodyVerified": False,
            "installationAuthorized": False, "releaseQualified": False,
            "productionQualified": False, "accepted": False,
            "status": "BLOCKED-external-qualification",
        }
        self.provider = {
            "kind": "sf-ci-provider-metadata-observation",
            "source": "github", "event": "merge_group",
            "candidateSha": "a" * 40, "runId": 123, "attempt": 1,
            "status": "provider-metadata-verified",
            "providerMetadataVerified": True,
            "independentPolicyDigestMatched": True,
            "checkoutSha": "unknown", "artifactBytesVerified": False,
            "independentPolicyVerified": False,
            "independentPolicyCustodyVerified": False,
            "effectAuthorized": False, "accepted": False,
        }

    def assess(self):
        return assess_supply_chain_handoff(
            self.intake, self.retained, self.provider,
            expected_source_commit="a" * 40, expected_source_tree="b" * 40,
            expected_artifact_sha256="c" * 64, expected_policy_sha256="d" * 64,
        )

    def test_consistent_observations_still_block_every_effect(self):
        result = self.assess()
        self.assertTrue(result["readOnlyObservationsConsistent"])
        for key in ("externalPublisherCustodyAuthenticated", "effectGrantVerified",
                    "releaseAuthorized", "deploymentAuthorized",
                    "productionQualified", "publishAuthorized", "accepted"):
            self.assertFalse(result[key])

    def test_cross_boundary_substitutions_fail(self):
        for record in (self.intake, self.retained):
            for key, invalid in (("sourceCommit", "1" * 40),
                                 ("sourceTree", "2" * 40),
                                 ("artifactSha256", "3" * 64),
                                 ("policySha256", "4" * 64)):
                with self.subTest(record=record["kind"], key=key):
                    original = record[key]
                    record[key] = invalid
                    with self.assertRaises(SupplyChainHandoffError):
                        self.assess()
                    record[key] = original

    def test_fabricated_authority_rejected(self):
        cases = (
            (self.intake, "productionQualified", True),
            (self.retained, "installationAuthorized", True),
            (self.retained, "exactRetainedBytesObserved", False),
            (self.provider, "effectAuthorized", True),
            (self.provider, "independentPolicyCustodyVerified", True),
            (self.provider, "checkoutSha", "a" * 40),
            (self.provider, "artifactBytesVerified", True),
        )
        for record, field, invalid in cases:
            with self.subTest(field=field):
                original = record[field]
                record[field] = invalid
                with self.assertRaises(SupplyChainHandoffError):
                    self.assess()
                record[field] = original

    def test_provider_wrong_event_and_run_fail(self):
        for field, invalid in (("candidateSha", "0" * 40),
                               ("event", "pull_request"),
                               ("runId", 0), ("attempt", 0),
                               ("providerMetadataVerified", False)):
            with self.subTest(field=field):
                original = self.provider[field]
                self.provider[field] = invalid
                with self.assertRaises(SupplyChainHandoffError):
                    self.assess()
                self.provider[field] = original


if __name__ == "__main__":
    unittest.main()
