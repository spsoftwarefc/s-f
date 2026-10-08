"""CI-13: acceptance outcomes must not be green from skipped/failing evidence."""
from __future__ import annotations

import contextlib
import io
import unittest

from tools.ci_acceptance import (
    BASELINE_MINIMUM, REQUIRED_TEST_IDS, _ids,
    accepts_platform_jobs, main, qualifies_tests,
)


def _passing_result() -> unittest.TestResult:
    result = unittest.TestResult()
    result.testsRun = len(_complete_inventory())
    return result


def _complete_inventory() -> set[str]:
    result = set(REQUIRED_TEST_IDS)
    result.update(f"additional.Fixture.test_{index}" for index in range(BASELINE_MINIMUM))
    return result


class CIAcceptanceTests(unittest.TestCase):
    def test_only_both_named_platform_successes_qualify(self):
        self.assertTrue(accepts_platform_jobs("success", "success"))
        for invalid in (None, "", "missing", "failure", "cancelled", "skipped",
                        "neutral", "pending", "timed_out", "action_required", "SUCCESS"):
            with self.subTest(value=invalid):
                self.assertFalse(accepts_platform_jobs(invalid, "success"))
                self.assertFalse(accepts_platform_jobs("success", invalid))

    def test_skipped_unittest_never_qualifies(self):
        result = _passing_result()
        result.skipped.append((None, "symlink not available on this platform"))
        self.assertFalse(qualifies_tests(result, _complete_inventory()))

    def test_expected_failure_never_qualifies(self):
        result = _passing_result()
        result.expectedFailures.append((None, "expected failure"))
        self.assertFalse(qualifies_tests(result, _complete_inventory()))

    def test_unexpected_success_never_qualifies(self):
        result = _passing_result()
        result.unexpectedSuccesses.append(None)
        self.assertFalse(qualifies_tests(result, _complete_inventory()))

    def test_actual_failure_and_error_never_qualify(self):
        for field in ("failures", "errors"):
            with self.subTest(field=field):
                result = _passing_result()
                getattr(result, field).append((None, "bad"))
                self.assertFalse(qualifies_tests(result, _complete_inventory()))

    def test_missing_critical_test_or_reduced_suite_never_qualifies(self):
        all_tests = _complete_inventory()
        self.assertTrue(qualifies_tests(_passing_result(), all_tests))
        one_missing = all_tests - {next(iter(REQUIRED_TEST_IDS))}
        self.assertFalse(qualifies_tests(_passing_result(), one_missing))
        fewer = _passing_result()
        fewer.testsRun = BASELINE_MINIMUM - 1
        self.assertFalse(qualifies_tests(fewer, all_tests))
        self.assertFalse(qualifies_tests(_passing_result(), set(REQUIRED_TEST_IDS)))

    def test_discovered_inventory_must_match_executed_tests(self):
        full = _complete_inventory()
        result = _passing_result()
        self.assertTrue(qualifies_tests(result, full))
        # Both counts remain greater than the 61-test minimum. The old gate
        # incorrectly accepted execution that silently omitted valid tests.
        result.testsRun = len(full) - 1
        self.assertGreater(result.testsRun, BASELINE_MINIMUM)
        self.assertFalse(qualifies_tests(result, full))
        result.testsRun = len(full) + 1
        self.assertFalse(qualifies_tests(result, full))

    def test_cli_exit_code_is_fail_closed(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["check-jobs", "--linux", "success", "--windows", "success"]), 0)
            self.assertEqual(main(["check-jobs", "--linux", "success", "--windows", "skipped"]), 1)
            self.assertEqual(main(["check-jobs", "--linux", "success"]), 1)
            self.assertEqual(main(["check-jobs"]), 1)

    def test_discovery_id_traversal(self):
        case = CIAcceptanceTests("test_cli_exit_code_is_fail_closed")
        group = unittest.TestSuite([unittest.TestSuite([case])])
        self.assertEqual(_ids(group), {case.id()})

    def test_ci15_provider_failure_probe(self):
        """Intentional temporary red check: must block main promotion."""
        self.fail("CI-15 controlled required-status-check enforcement probe")

    def test_current_critical_tests_present_in_discovery(self):
        suite = unittest.TestLoader().discover(start_dir="tests", pattern="test_*.py")
        found = _ids(suite)
        self.assertGreaterEqual(len(found), BASELINE_MINIMUM)
        self.assertFalse(REQUIRED_TEST_IDS - found)
