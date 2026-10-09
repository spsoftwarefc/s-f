"""PQ-07V source declarations cannot qualify a real service."""
import copy
import unittest

from sf.reference_target_contract import FAULTS, TargetContractError, inspect_target_contract


class ReferenceTargetContractTests(unittest.TestCase):
    def setUp(self):
        self.contract = {
            "schemaVersion": 1, "kind": "sf-pq07v-proposed-reference-target",
            "sourceCommit": "a" * 40, "sourceTree": "b" * 40,
            "artifactSha256": "c" * 64, "ownerId": "operator", "targetId": "disposable01",
            "platform": "linux", "environment": "test",
            "backend": "disposable-single-host", "disposable": True,
            "capabilities": {
                "destinationAtomicCAS": True, "destinationIdempotency": True,
                "authenticatedStatus": True, "rollbackBoundaryDeclared": True,
            },
            "limits": {"maxMemoryMiB": 128, "maxDiskMiB": 256,
                       "maxDurationSeconds": 600},
            "faultCases": [{"case": case, "state": "planned"} for case in FAULTS],
        }

    def inspect(self):
        return inspect_target_contract(
            self.contract, expected_source_commit="a" * 40,
            expected_source_tree="b" * 40, expected_artifact_sha256="c" * 64,
        )

    def test_declaration_always_no_go(self):
        result = self.inspect()
        self.assertTrue(result["capabilitiesDeclared"])
        self.assertEqual(result["faultCaseCount"], len(FAULTS))
        for key in ("actualTargetOwnershipAuthenticated", "destinationCASVerified",
                    "remoteReceiptAuthenticated", "liveFaultCasesExecuted",
                    "liveRecoveryQualified", "externalEffectAuthorized",
                    "productionQualified", "accepted"):
            self.assertFalse(result[key])

    def test_production_target_and_wrong_scope_rejected(self):
        for key, bad in (("environment", "production"), ("disposable", False),
                         ("backend", "remote-production-vps"),
                         ("platform", "windows"), ("sourceCommit", "0" * 40)):
            with self.subTest(key=key):
                original = self.contract[key]
                self.contract[key] = bad
                with self.assertRaises(TargetContractError):
                    self.inspect()
                self.contract[key] = original

    def test_capability_missing_or_false(self):
        for key in tuple(self.contract["capabilities"]):
            old = self.contract["capabilities"][key]
            self.contract["capabilities"][key] = False
            with self.assertRaises(TargetContractError):
                self.inspect()
            self.contract["capabilities"][key] = old
        self.contract["capabilities"]["liveAuthenticated"] = True
        with self.assertRaises(TargetContractError):
            self.inspect()

    def test_fault_cases_incomplete_forged_and_out_of_order(self):
        cases = self.contract["faultCases"]
        for bad in (cases[:-1], [{**cases[0], "state": "passed"}] + cases[1:],
                    list(reversed(cases)), cases + [cases[0]]):
            self.contract["faultCases"] = bad
            with self.assertRaises(TargetContractError):
                self.inspect()

    def test_budget_and_extra_rights_rejected(self):
        for key, value in (("maxMemoryMiB", 8192),
                           ("maxDiskMiB", -1), ("maxDurationSeconds", 9999)):
            original = self.contract["limits"][key]
            self.contract["limits"][key] = value
            with self.assertRaises(TargetContractError):
                self.inspect()
            self.contract["limits"][key] = original
        self.contract["approved"] = True
        with self.assertRaises(TargetContractError):
            self.inspect()


if __name__ == "__main__":
    unittest.main()
