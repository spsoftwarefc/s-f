"""SF-15: independent fake-target invariants, adverse event traces and CLI."""
from __future__ import annotations

import contextlib
import copy
import io
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sf.cli import main
from sf.deployment import (
    DeploymentError, FakeCoordinator, FakeTarget, MemoryLedger, SimulatedCrash,
    SCENARIOS, _intent, qualify_deployment, run_scenario, validate_release_plan,
)


def release_plan():
    return {
        "schemaVersion": 1, "kind": "sf-offline-release-plan",
        "status": "matches-external-approval-pin-not-authenticated",
        "source": {"repository": "example/factory-fixture",
                   "commit": "a" * 40, "tree": "b" * 40},
        "sourceCheckoutVerified": True,
        "artifact": {"kind": "archive", "sha256": "c" * 64},
        "ci": {"runId": 200, "attempt": 1, "receiptSha256": "d" * 64,
               "providerMetadataClaimReverifiedLive": False},
        "destination": {"targetId": "fake-target", "environment": "staging",
                        "adapter": "inmemory"},
        "authorization": {"principal": "operator-1", "grantId": "grant-001",
                          "expiresOn": "2099-01-01"},
        "migration": {"path": "plans/migrate.json", "sha256": "e" * 64,
                      "disposition": "forward"},
        "recovery": {"path": "plans/recover.json", "sha256": "f" * 64,
                     "disposition": "restore"},
        "requestSha256": "1" * 64, "externalApprovalPinSha256": "2" * 64,
        "approvedReleaseOriginAuthenticated": False,
        "independentSourceAcceptanceVerified": False,
        "deploymentAuthorized": False, "artifactDeployed": False,
        "releaseQualified": False, "accepted": False, "readOnly": True,
    }


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.plan = release_plan()
        self.today = date(2026, 10, 8)
        self.target = FakeTarget(self.plan["destination"])
        self.ledger = MemoryLedger()
        self.owner = self.plan["authorization"]["principal"]
        self.coordinator = FakeCoordinator(self.ledger, self.target, today=self.today)

    def start(self, **kwargs):
        return self.coordinator.start(self.plan, owner=self.owner, epoch=1, **kwargs)

    def recover(self, **kwargs):
        return self.coordinator.recover(owner=self.owner, epoch=1, **kwargs)

    def test_all_twelve_independent_scenarios_and_no_live_authority(self):
        out = qualify_deployment(self.plan, today=self.today)
        self.assertEqual(out["scenariosRequired"], 12)
        self.assertEqual(out["scenariosPassed"], 12)
        self.assertEqual({x["scenario"] for x in out["cases"]}, set(SCENARIOS))
        self.assertTrue(all(x["passed"] for x in out["cases"]))
        self.assertTrue(out["syntheticPassed"])
        for name in ("realTargetExercised", "externalAuthorityAuthenticated",
                     "diskDurabilityVerified", "distributedFenceQualified",
                     "accepted", "deploymentAuthorized", "releaseQualified"):
            self.assertIs(out[name], False)

    def test_campaign_is_deterministic_and_does_not_mutate_input(self):
        original = copy.deepcopy(self.plan)
        left = qualify_deployment(self.plan, today=self.today)
        right = qualify_deployment(self.plan, today=self.today)
        self.assertEqual(left, right)
        self.assertEqual(self.plan, original)

    def test_prepared_before_dispatch_and_exact_idempotency(self):
        record = self.start()
        self.assertEqual(record["state"], "HEALTHY")
        self.assertEqual(record["events"][:3],
                         ["intent-persisted", "migration-simulated", "dispatch-intent-persisted"])
        self.assertEqual(record["events"][-2:], ["dispatch-receipt-confirmed", "health-confirmed"])
        self.assertEqual(self.target.dispatch_count, 1)
        self.assertEqual(self.target.applied[_intent(self.plan)]["artifactSha256"],
                         self.plan["artifact"]["sha256"])

    def test_concurrent_owner_denied_before_target_dispatch(self):
        self.ledger.acquire("external-owner", 1)
        with self.assertRaisesRegex(DeploymentError, "concurrent"):
            self.coordinator.start(self.plan, owner=self.owner, epoch=2)
        self.assertEqual(self.target.dispatch_count, 0)
        self.assertIsNone(self.ledger.record)

    def test_revoked_grant_denied_before_fence_or_journal(self):
        with self.assertRaisesRegex(DeploymentError, "revoked"):
            self.start(revoked=True)
        self.assertEqual(self.target.fence, 0)
        self.assertIsNone(self.ledger.record)

    def test_expired_grant_blocks_start_and_recovery(self):
        expired = copy.deepcopy(self.plan)
        expired["authorization"]["expiresOn"] = "2020-01-01"
        with self.assertRaisesRegex(DeploymentError, "stale"):
            self.coordinator.start(expired, owner=self.owner, epoch=1)
        with self.assertRaises(DeploymentError):
            self.coordinator.start(self.plan, owner=self.owner, epoch=1, fault="crash")
        # The preceding simulated crash leaves an unresolved dispatch.
        newer = FakeCoordinator(self.ledger, self.target, today=date(2100, 1, 1))
        with self.assertRaisesRegex(DeploymentError, "stale"):
            newer.recover(owner=self.owner, epoch=1)
        self.assertEqual(self.target.dispatch_count, 1)

    def test_wrong_principal_and_wrong_destination_denied(self):
        with self.assertRaisesRegex(DeploymentError, "principal"):
            self.coordinator.start(self.plan, owner="another-operator", epoch=1)
        self.target.destination["targetId"] = "other-target"
        with self.assertRaisesRegex(DeploymentError, "wrong target"):
            self.start()
        self.assertIsNone(self.ledger.record)

    def test_stale_target_fencing_prevents_dispatch(self):
        self.target.reserve_fence(2)
        with self.assertRaisesRegex(DeploymentError, "stale target"):
            self.start()
        self.assertEqual(self.target.dispatch_count, 0)
        self.assertIsNone(self.ledger.record)

    def test_migration_failure_before_dispatch_has_no_artifact_effect(self):
        result = self.start(fault="migration")
        self.assertEqual(result["state"], "MIGRATION_FAILED")
        self.assertNotIn("dispatch-intent-persisted", result["events"])
        self.assertEqual(self.target.dispatch_count, 0)
        self.assertIsNone(self.target.active_artifact)

    def test_migration_after_effect_is_unknown_and_never_deploys(self):
        result = self.start(fault="migration-after")
        self.assertEqual(result["state"], "MIGRATION_UNKNOWN")
        self.assertIn(result["intentKey"], self.target.migration_keys)
        self.assertEqual(self.target.dispatch_count, 0)
        with self.assertRaisesRegex(DeploymentError, "unsettled"):
            self.coordinator.start(self.plan, owner=self.owner, epoch=2)

    def test_crash_after_send_reconciles_without_second_dispatch(self):
        with self.assertRaises(SimulatedCrash):
            self.start(fault="crash")
        self.assertEqual(self.ledger.record["state"], "DISPATCHED")
        self.assertEqual(self.target.dispatch_count, 1)
        restarted = FakeCoordinator(self.ledger, self.target, today=self.today)
        result = restarted.recover(owner=self.owner, epoch=1)
        self.assertEqual(result["state"], "HEALTHY")
        self.assertIn("target-receipt-reconciled", result["events"])
        self.assertEqual(self.target.dispatch_count, 1)

    def test_unknown_response_resolved_by_exact_target_receipt(self):
        result = self.start(fault="unknown")
        self.assertEqual(result["state"], "UNKNOWN")
        resumed = self.recover()
        self.assertEqual(resumed["state"], "HEALTHY")
        self.assertEqual(self.target.dispatch_count, 1)

    def test_missing_target_receipt_remains_unknown_no_blind_retry(self):
        self.start(fault="unknown")
        self.target.applied.clear()
        result = self.recover()
        self.assertEqual(result["state"], "UNKNOWN")
        self.assertIn("authoritative-receipt-absent-no-retry", result["events"])
        self.assertEqual(self.target.dispatch_count, 1)

    def test_unavailable_target_query_remains_unknown(self):
        self.start(fault="unknown")
        self.target.reconcile_available = False
        self.assertEqual(self.recover()["state"], "UNKNOWN")
        self.assertEqual(self.target.dispatch_count, 1)

    def test_forged_target_receipt_is_quarantined(self):
        self.start(fault="unknown")
        key = self.ledger.record["intentKey"]
        self.target.applied[key]["artifactSha256"] = "0" * 64
        state = self.recover()
        self.assertEqual(state["state"], "RECOVERY_BLOCKED")
        self.assertEqual(self.target.dispatch_count, 1)

    def test_forged_ledger_identity_cannot_be_recovered(self):
        self.start(fault="unknown")
        self.ledger.record["plan"]["source"]["commit"] = "0" * 40
        with self.assertRaisesRegex(DeploymentError, "corrupt persisted"):
            self.recover()
        self.assertEqual(self.target.dispatch_count, 1)

    def test_recovery_wrong_epoch_and_revoked_authorization(self):
        self.start(fault="unknown")
        with self.assertRaisesRegex(DeploymentError, "recovery owner or epoch"):
            self.coordinator.recover(owner=self.owner, epoch=2)
        with self.assertRaisesRegex(DeploymentError, "revoked"):
            self.recover(revoked=True)
        self.assertEqual(self.target.dispatch_count, 1)

    def test_health_failure_does_not_qualify_release(self):
        state = self.start(fault="health")
        self.assertEqual(state["state"], "UNHEALTHY")
        self.assertEqual(self.target.dispatch_count, 1)
        self.assertIn("health-rejected", state["events"])
        self.assertIsNotNone(self.target.active_artifact)
        self.assertNotIn("compensation-confirmed", state["events"])

    def test_compensation_requires_unhealthy_verified_effect(self):
        with self.assertRaises(DeploymentError):
            self.coordinator.compensate(owner=self.owner, epoch=1)
        self.start(fault="health")
        prior = self.ledger.record["previousArtifact"]
        result = self.coordinator.compensate(owner=self.owner, epoch=1)
        self.assertEqual(result["state"], "COMPENSATED")
        self.assertEqual(self.target.active_artifact, prior)
        self.assertIn("recovery-intent-persisted", result["events"])
        with self.assertRaises(DeploymentError):
            self.coordinator.compensate(owner=self.owner, epoch=1)

    def test_unknown_compensation_cannot_be_blindly_replayed(self):
        self.start(fault="health")
        self.target.compensation_unknown = True
        result = self.coordinator.compensate(owner=self.owner, epoch=1)
        self.assertEqual(result["state"], "COMPENSATION_UNKNOWN")
        self.assertEqual(self.recover()["state"], "COMPENSATION_UNKNOWN")
        self.assertEqual(self.target.dispatch_count, 1)

    def test_target_fence_supersedes_stale_recovery(self):
        self.start(fault="unknown")
        self.target.reserve_fence(2)
        with self.assertRaisesRegex(DeploymentError, "superseded"):
            self.recover()

    def test_idempotency_key_cannot_be_reused_for_different_effect(self):
        self.start()
        key = self.ledger.record["intentKey"]
        altered = copy.deepcopy(self.plan)
        altered["artifact"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(DeploymentError, "idempotency collision"):
            self.target.dispatch(key=key, epoch=1, plan=altered)
        self.assertEqual(self.target.dispatch_count, 1)

    def test_untrusted_or_malformed_release_plans_fail(self):
        variants = []
        for key in ("deploymentAuthorized", "accepted", "releaseQualified",
                    "approvedReleaseOriginAuthenticated", "independentSourceAcceptanceVerified"):
            candidate = copy.deepcopy(self.plan)
            candidate[key] = True
            variants.append(candidate)
        candidate = copy.deepcopy(self.plan)
        candidate["unexpected"] = "authority"
        variants.append(candidate)
        candidate = copy.deepcopy(self.plan)
        candidate["artifact"]["sha256"] = "wrong"
        variants.append(candidate)
        candidate = copy.deepcopy(self.plan)
        candidate["destination"]["targetId"] = "../escape"
        variants.append(candidate)
        for variant in variants:
            with self.subTest(variant=variant):
                with self.assertRaises(DeploymentError):
                    validate_release_plan(variant)

    def test_cli_qualify_uses_only_supplied_local_fixture(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "plan.json"
            path.write_text(json.dumps(self.plan, sort_keys=True))
            before = path.read_bytes()
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                result = main(["deployment", "qualify", "--plan", str(path)])
            self.assertEqual(result, 0)
            parsed = json.loads(out.getvalue())
            self.assertEqual(parsed["scenariosPassed"], 12)
            self.assertFalse(parsed["realTargetExercised"])
            self.assertFalse(parsed["deploymentAuthorized"])
            self.assertEqual(path.read_bytes(), before)

    def test_cli_malformed_input_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "plan.json"
            path.write_text('{"schemaVersion": 1, "schemaVersion": 1}')
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(["deployment", "qualify", "--plan", str(path)]), 2)

    def test_scenario_contract_rejects_unexpected_fault(self):
        with self.assertRaisesRegex(DeploymentError, "unsupported"):
            self.start(fault="shell")
        with self.assertRaisesRegex(DeploymentError, "unsupported"):
            run_scenario(self.plan, "actual-production", today=self.today)


if __name__ == "__main__":
    unittest.main()
