"""SF-16: independent offline observation, incident and work-feedback tests."""
from __future__ import annotations

import contextlib
import copy
import io
import json
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from sf.cli import main
from sf.deployment import qualify_deployment
from sf.operations import (
    DOMAINS, OperationsError, assess_operations, read_document,
)


def fixture_release():
    """Synthetic, deliberately unqualified SF-14 plan; not real acceptance."""
    return {
        "schemaVersion": 1, "kind": "sf-offline-release-plan",
        "status": "matches-external-approval-pin-not-authenticated",
        "source": {"repository": "example/fake-repo", "commit": "a" * 40,
                   "tree": "b" * 40}, "sourceCheckoutVerified": True,
        "artifact": {"kind": "archive", "sha256": "c" * 64},
        "ci": {"runId": 17, "attempt": 1, "receiptSha256": "d" * 64,
               "providerMetadataClaimReverifiedLive": False},
        "destination": {"targetId": "isolated-target", "environment": "test",
                        "adapter": "inmemory"},
        "authorization": {"principal": "operator-1", "grantId": "grant-17",
                          "expiresOn": "2099-01-01"},
        "migration": {"path": "plans/migrate.json", "sha256": "e" * 64,
                      "disposition": "forward"},
        "recovery": {"path": "plans/recover.json", "sha256": "f" * 64,
                     "disposition": "restore"},
        "requestSha256": "1" * 64, "externalApprovalPinSha256": "2" * 64,
        "approvedReleaseOriginAuthenticated": False,
        "independentSourceAcceptanceVerified": False, "deploymentAuthorized": False,
        "artifactDeployed": False, "releaseQualified": False, "accepted": False,
        "readOnly": True,
    }


class OperationsTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 8, 20, 0, 0, tzinfo=timezone.utc)
        self.qual = qualify_deployment(fixture_release(), today=date(2026, 10, 8))
        self.assertEqual(self.qual["scenariosPassed"], 12)
        self.policy = {
            "schemaVersion": 1, "kind": "sf16-operations-policy",
            "sourceCommit": self.qual["source"]["commit"],
            "planSha256": self.qual["planSha256"],
            "destination": copy.deepcopy(self.qual["destination"]),
            "maxEventAgeSeconds": 300, "maxEvents": 32, "recoveryHealthyCount": 2,
            "routes": {
                "deployment": {"ownerId": "oncall-deploy", "runbookId": "rb-deploy"},
                "health": {"ownerId": "oncall-health", "runbookId": "rb-health"},
                "migration": {"ownerId": "oncall-data", "runbookId": "rb-migration"},
                "recovery": {"ownerId": "oncall-recovery", "runbookId": "rb-recovery"},
            },
        }
        self.events = {
            "schemaVersion": 1, "kind": "sf16-offline-observations",
            "sourceCommit": self.qual["source"]["commit"],
            "planSha256": self.qual["planSha256"],
            "destination": copy.deepcopy(self.qual["destination"]),
            "events": [],
        }
        self.n = 0

    def add(self, domain, state, *, offset=-30, identifier=None):
        self.n += 1
        entry = {
            "eventId": identifier or "ev-" + str(self.n),
            "observedAt": (self.now + timedelta(seconds=offset))
                .strftime("%Y-%m-%dT%H:%M:%SZ"),
            "domain": domain, "state": state, "evidenceSha256": "f" * 64,
        }
        self.events["events"].append(entry)
        return entry

    def inspect(self):
        return assess_operations(self.qual, self.policy, self.events, now=self.now)

    def test_missing_observations_are_unknown_and_not_healthy(self):
        result = self.inspect()
        self.assertEqual(result["status"], "observation-incomplete")
        self.assertEqual(result["eventsObserved"], 0)
        self.assertEqual(len(result["health"]), 4)
        self.assertEqual([x["status"] for x in result["health"]], ["unknown"] * 4)
        self.assertEqual(result["incidents"], [])
        self.assertEqual(result["workItemProposals"], [])
        self.assertFalse(result["liveHealthVerified"])
        self.assertFalse(result["deploymentAuthorized"])

    def test_all_fresh_healthy_only_observed_not_live_verified(self):
        for domain in DOMAINS:
            self.add(domain, "healthy", offset=-29)
        outcome = self.inspect()
        self.assertEqual(outcome["status"], "healthy-observed-unverified")
        self.assertEqual([x["status"] for x in outcome["health"]],
                         ["healthy-observed"] * 4)
        self.assertTrue(all(x["fresh"] for x in outcome["health"]))
        self.assertFalse(outcome["liveHealthVerified"])
        self.assertFalse(outcome["accepted"])
        self.assertFalse(outcome["releaseQualified"])

    def test_failed_health_routes_to_owner_and_runbook_without_external_work(self):
        self.add("health", "failed", offset=-30)
        result = self.inspect()
        self.assertEqual(result["status"], "incident-review-required")
        self.assertEqual(len(result["incidents"]), 1)
        issue = result["incidents"][0]
        self.assertEqual(issue["domain"], "health")
        self.assertEqual(issue["severity"], "critical")
        self.assertEqual(issue["ownerId"], "oncall-health")
        self.assertEqual(issue["runbookId"], "rb-health")
        self.assertEqual(issue["status"], "open-review-required")
        self.assertFalse(issue["acknowledged"])
        self.assertFalse(issue["resolved"])
        proposal = result["workItemProposals"][0]
        self.assertEqual(proposal["incidentId"], issue["incidentId"])
        self.assertFalse(proposal["created"])
        self.assertTrue(proposal["requiresOperatorApproval"])
        self.assertFalse(result["notificationsSent"])
        self.assertFalse(result["workItemsCreated"])

    def test_unknown_recovery_is_high_and_not_reported_successful(self):
        self.add("recovery", "unknown")
        result = self.inspect()
        self.assertEqual(result["incidents"][0]["severity"], "high")
        self.assertEqual(result["incidents"][0]["domain"], "recovery")
        self.assertEqual(next(x for x in result["health"] if x["domain"] == "recovery")["status"],
                         "unknown")
        self.assertEqual(result["incidents"][0]["runbookId"], "rb-recovery")

    def test_degradation_is_medium_not_critical(self):
        self.add("deployment", "degraded")
        issue = self.inspect()["incidents"][0]
        self.assertEqual(issue["severity"], "medium")

    def test_recovery_requires_two_consecutive_healthy_and_human_closure(self):
        self.add("health", "failed", offset=-100)
        first = self.inspect()
        issue_id = first["incidents"][0]["incidentId"]
        work_id = first["workItemProposals"][0]["proposalId"]
        self.add("health", "healthy", offset=-60)
        middle = self.inspect()
        self.assertEqual(middle["health"][1]["status"], "unresolved")
        self.assertFalse(middle["incidents"][0]["recoveryEvidenceEligible"])
        self.add("health", "healthy", offset=-20)
        last = self.inspect()
        self.assertEqual(last["health"][1]["status"], "recovery-review")
        self.assertEqual(last["incidents"][0]["status"], "recovery-review-required")
        self.assertEqual(last["incidents"][0]["incidentId"], issue_id)
        self.assertEqual(last["workItemProposals"][0]["proposalId"], work_id)
        self.assertTrue(last["incidents"][0]["recoveryEvidenceEligible"])
        self.assertFalse(last["incidents"][0]["resolved"])
        self.assertFalse(last["health"][1]["incidentClosureAuthorized"])

    def test_one_healthy_observation_never_closes_incident(self):
        self.add("migration", "degraded", offset=-60)
        self.add("migration", "healthy", offset=-10)
        report = self.inspect()
        self.assertEqual(next(x for x in report["health"] if x["domain"] == "migration")["status"],
                         "unresolved")
        self.assertFalse(report["incidents"][0]["resolved"])

    def test_stale_observation_is_unknown_not_green(self):
        self.add("health", "healthy", offset=-301)
        report = self.inspect()
        item = next(x for x in report["health"] if x["domain"] == "health")
        self.assertEqual(item["status"], "unknown")
        self.assertEqual(item["reason"], "stale-observations")
        self.assertFalse(item["fresh"])
        self.assertEqual(report["status"], "observation-incomplete")

    def test_stale_failed_incident_cannot_auto_resolve(self):
        self.add("health", "failed", offset=-1000)
        report = self.inspect()
        self.assertEqual(report["health"][1]["status"], "unknown")
        self.assertEqual(len(report["incidents"]), 1)
        self.assertEqual(report["incidents"][0]["status"], "open-review-required")
        self.assertFalse(report["incidents"][0]["resolved"])

    def test_idempotent_proposal_and_untrusted_digest_bound_to_snapshot(self):
        self.add("deployment", "unknown")
        first = self.inspect()
        second = self.inspect()
        self.assertEqual(first, second)
        self.add("deployment", "healthy", offset=-10)
        third = self.inspect()
        self.assertEqual(third["workItemProposals"][0]["proposalId"],
                         first["workItemProposals"][0]["proposalId"])
        self.assertNotEqual(third["observationDigest"], first["observationDigest"])

    def test_multiple_domains_at_most_four_proposals(self):
        for domain in DOMAINS:
            self.add(domain, "failed", offset=-50)
        result = self.inspect()
        self.assertEqual(len(result["incidents"]), len(DOMAINS))
        self.assertEqual(len(result["workItemProposals"]), len(DOMAINS))
        self.assertEqual(len({x["incidentId"] for x in result["incidents"]}), len(DOMAINS))
        self.assertTrue(all(x["requiresOperatorApproval"] for x in result["workItemProposals"]))

    def test_mixed_health_with_missing_domains_is_incomplete(self):
        self.add("health", "healthy")
        result = self.inspect()
        self.assertEqual(result["status"], "observation-incomplete")

    def test_oversized_count_blocks_entire_assessment(self):
        self.policy["maxEvents"] = 2
        for i in range(3):
            self.add("health", "healthy", offset=-30 + i)
        with self.assertRaisesRegex(OperationsError, "event budget"):
            self.inspect()

    def test_duplicate_event_id_fails_even_if_other_fields_change(self):
        self.add("health", "degraded", offset=-40, identifier="same-id")
        self.add("health", "healthy", offset=-20, identifier="same-id")
        with self.assertRaisesRegex(OperationsError, "duplicate"):
            self.inspect()

    def test_out_of_order_and_future_observation_rejected(self):
        self.add("recovery", "unknown", offset=-15)
        self.add("recovery", "healthy", offset=-25)
        with self.assertRaisesRegex(OperationsError, "out-of-order"):
            self.inspect()
        self.events["events"].clear()
        self.add("health", "healthy", offset=1)
        with self.assertRaisesRegex(OperationsError, "future"):
            self.inspect()

    def test_unexpected_domain_or_state_or_unbounded_prompt_rejected(self):
        for field, replacement in (("domain", "remote-shell"), ("state", "launch-now"),
                                   ("evidenceSha256", "not-a-digest")):
            with self.subTest(field=field):
                self.events["events"].clear()
                row = self.add("health", "healthy")
                row[field] = replacement
                with self.assertRaises(OperationsError):
                    self.inspect()
        self.events["events"].clear()
        row = self.add("health", "healthy")
        row["freeformCommand"] = "deploy to production"
        with self.assertRaisesRegex(OperationsError, "unknown fields"):
            self.inspect()

    def test_qualification_cannot_promote_trust(self):
        for key in ("accepted", "deploymentAuthorized", "releaseQualified",
                    "realTargetExercised", "externalAuthorityAuthenticated",
                    "diskDurabilityVerified", "distributedFenceQualified"):
            with self.subTest(key=key):
                q = copy.deepcopy(self.qual)
                q[key] = True
                with self.assertRaises(OperationsError):
                    assess_operations(q, self.policy, self.events, now=self.now)

    def test_incomplete_or_substituted_fake_scenarios_block(self):
        q = copy.deepcopy(self.qual)
        q["cases"][0]["passed"] = False
        with self.assertRaises(OperationsError):
            assess_operations(q, self.policy, self.events, now=self.now)
        q = copy.deepcopy(self.qual)
        q["cases"][0]["observed"] = "ERROR"
        with self.assertRaises(OperationsError):
            assess_operations(q, self.policy, self.events, now=self.now)

    def test_cross_target_source_and_plan_substitution_blocked(self):
        for subject in ("policy", "observations"):
            for field in ("sourceCommit", "planSha256"):
                with self.subTest(subject=subject, field=field):
                    obj = copy.deepcopy(self.policy if subject == "policy" else self.events)
                    obj[field] = ("a" if field == "planSha256" else "b") * (
                        64 if field == "planSha256" else 40)
                    if subject == "policy":
                        with self.assertRaises(OperationsError):
                            assess_operations(self.qual, obj, self.events, now=self.now)
                    else:
                        with self.assertRaises(OperationsError):
                            assess_operations(self.qual, self.policy, obj, now=self.now)
        self.events["destination"]["targetId"] = "different-target"
        with self.assertRaisesRegex(OperationsError, "substitution"):
            self.inspect()

    def test_invalid_routes_and_thresholds_block(self):
        self.policy["routes"]["health"]["ownerId"] = "operator;rm -rf /"
        with self.assertRaises(OperationsError):
            self.inspect()
        self.policy["routes"]["health"]["ownerId"] = "oncall-health"
        self.policy["maxEventAgeSeconds"] = 0
        with self.assertRaises(OperationsError):
            self.inspect()

    def test_naive_clock_and_non_utc_clock_rejected(self):
        with self.assertRaisesRegex(OperationsError, "clock"):
            assess_operations(self.qual, self.policy, self.events,
                              now=datetime(2026, 10, 8, 20, 0))

    def test_read_document_rejects_duplicate_keys_oversize_and_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "data.json"
            path.write_text('{"events": [], "events": []}')
            with self.assertRaisesRegex(OperationsError, "duplicate"):
                read_document(path)
            path.write_bytes(b"x" * (256 * 1024 + 1))
            with self.assertRaisesRegex(OperationsError, "oversized"):
                read_document(path)
            real = Path(d) / "actual.json"
            real.write_text("{}")
            path.unlink()
            try:
                path.symlink_to(real)
            except (NotImplementedError, OSError):
                return  # Windows may disallow creating symlinks.
            with self.assertRaises(OperationsError):
                read_document(path)

    def test_cli_offline_snapshot_and_incident_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            temp = Path(d)
            files = [temp / "qualification.json", temp / "policy.json",
                     temp / "observations.json"]
            self.events["events"] = []
            actual_now = datetime.now(timezone.utc).replace(microsecond=0)
            for domain in DOMAINS:
                self.n += 1
                self.events["events"].append({
                    "eventId": "now-" + str(self.n),
                    "observedAt": (actual_now - timedelta(seconds=10))
                        .strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "domain": domain, "state": "healthy",
                    "evidenceSha256": "f" * 64,
                })
            for path, data in zip(files, (self.qual, self.policy, self.events)):
                path.write_text(json.dumps(data))
            args = ["operations", "assess", "--qualification", str(files[0]),
                    "--policy", str(files[1]), "--observations", str(files[2])]
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(args), 0)
            parsed = json.loads(output.getvalue())
            self.assertEqual(parsed["status"], "healthy-observed-unverified")
            self.assertFalse(parsed["liveHealthVerified"])
            self.assertFalse(parsed["notificationsSent"])
            self.assertFalse(parsed["workItemsCreated"])
            self.events["events"][0]["state"] = "failed"
            files[2].write_text(json.dumps(self.events))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(args), 1)
            self.assertEqual([p.name for p in temp.iterdir()],
                             [p.name for p in files])

    def test_cli_bad_input_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            q, p, e = (Path(d) / x for x in ("q.json", "p.json", "e.json"))
            q.write_text('{"x": 1, "x": 2}')
            p.write_text(json.dumps(self.policy))
            e.write_text(json.dumps(self.events))
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(["operations", "assess", "--qualification", str(q),
                                       "--policy", str(p), "--observations", str(e)]), 2)


if __name__ == "__main__":
    unittest.main()
