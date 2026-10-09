"""PQ-05 reference-target atomic CAS/idempotency tests."""
import tempfile
import unittest
from pathlib import Path

from sf.reference_target import ReferenceTarget, ReferenceTargetError


class ReferenceTargetTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "target.db"

    def test_same_operation_after_lost_reply_and_restart(self):
        with ReferenceTarget(self.path) as one:
            receipt = one.apply("op1", 1, "a" * 64, None)
            self.assertEqual(receipt["state"], "APPLIED")
            self.assertEqual(one.apply("op1", 1, "a" * 64, None), receipt)
        with ReferenceTarget(self.path) as two:
            self.assertEqual(two.status("op1"), receipt)
            self.assertEqual(two.snapshot()["artifactSha256"], "a" * 64)
            self.assertFalse(two.snapshot()["productionDeploymentQualified"])

    def test_stale_generation_and_cas_reject_without_change(self):
        with ReferenceTarget(self.path) as target:
            target.apply("op1", 5, "a" * 64, None)
            with self.assertRaises(ReferenceTargetError):
                target.apply("op2", 4, "b" * 64, "a" * 64)
            with self.assertRaises(ReferenceTargetError):
                target.apply("op2", 6, "b" * 64, None)
            self.assertEqual(target.snapshot()["generation"], 5)
            self.assertEqual(target.snapshot()["artifactSha256"], "a" * 64)

    def test_conflicting_reuse_and_competing_connections(self):
        with ReferenceTarget(self.path) as one, ReferenceTarget(self.path) as two:
            one.apply("op1", 1, "a" * 64, None)
            with self.assertRaises(ReferenceTargetError):
                two.apply("op1", 2, "b" * 64, "a" * 64)
            other = two.apply("op2", 2, "b" * 64, "a" * 64)
            self.assertEqual(other["previousSha256"], "a" * 64)

    def test_malformed_target_effect_denied(self):
        with ReferenceTarget(self.path) as target:
            with self.assertRaises(ReferenceTargetError):
                target.apply("../bad", 1, "a" * 64, None)
            with self.assertRaises(ReferenceTargetError):
                target.apply("op1", 0, "a" * 64, None)
            with self.assertRaises(ReferenceTargetError):
                target.apply("op1", 1, "bad", None)


if __name__ == "__main__":
    unittest.main()
