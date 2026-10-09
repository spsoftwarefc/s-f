"""PQ-07Q uses real local subprocess exit, never a network service."""
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from sf.reference_campaign import (
    ReferenceCampaignError, exercise_local_reference,
)


class LocalDeathTests(unittest.TestCase):
    def test_commit_survives_real_child_exit_and_rejects_stale_fence(self):
        report = exercise_local_reference()
        self.assertTrue(report["localProcessExitObserved"])
        self.assertTrue(report["localReceiptRecovered"])
        self.assertTrue(report["localStaleAndConflictingEffectsRejected"])
        for field in ("realRemoteFenceQualified", "authenticatedChannelVerified",
                      "realServiceDeployed", "liveOperationsVerified",
                      "recoveryForPowerLossQualified", "productionQualified"):
            with self.subTest(field=field):
                self.assertIs(report[field], False)

    def test_child_does_not_claim_success_unless_expected_exit(self):
        with patch("sf.reference_campaign.subprocess.run",
                   return_value=SimpleNamespace(returncode=0)):
            with self.assertRaises(ReferenceCampaignError):
                exercise_local_reference()


if __name__ == "__main__":
    unittest.main()
