"""CI-13: local acceptance predicates and strict, zero-skip unittest runner.

This is candidate-controlled code; it cannot attest provider identity or GitHub ruleset
enforcement. The actual GitHub Actions job results and queue identity must be verified
from GitHub, and any change to this checker must undergo recorded operator review.
"""
from __future__ import annotations

import argparse
import json
import sys
import unittest
from pathlib import Path

BASELINE_MINIMUM = 61
REQUIRED_TEST_IDS = frozenset({
    "test_profile.ProfileTests.test_path_escape",
    "test_inventory.InventoryTests.test_symlink_not_followed",
    "test_adapters.AdaptersTests.test_untrusted_command_is_not_executed",
    "test_integration.IntegrationTests.test_dry_run_no_writes_and_stable_serialization",
    "test_integration.IntegrationTests.test_existing_project_instructions_and_ci_preserved",
    "test_integration.IntegrationTests.test_casefold_collision_blocks_route_and_owned_namespace",
    "test_integration.IntegrationTests.test_known_owned_repeat_plan_is_noop_and_modified_owned_file_is_blocked",
    "test_lifecycle.LifecycleTests.test_stale_or_forged_plan_fails_without_writing",
    "test_lifecycle.LifecycleTests.test_interrupt_after_first_effect_recover_idempotently",
    "test_lifecycle.LifecycleTests.test_interrupted_target_modified_recovery_quarantines",
    "test_lifecycle.LifecycleTests.test_upgrade_preserves_locally_modified_owned_file",
    "test_lifecycle.LifecycleTests.test_remove_modified_owned_blocks_entire_operation",
    "test_lifecycle.LifecycleTests.test_forged_journal_blocked",
    "test_lifecycle.LifecycleTests.test_remove_crash_recover",
    "test_portability.PortabilityTests.test_existing_node_ui_with_custom_ci_preserved",
    "test_portability.PortabilityTests.test_monorepo_with_dependency_order_and_no_executions",
    "test_portability.PortabilityTests.test_path_symlink_escape_blocks",
    "test_portability.PortabilityTests.test_crash_requires_recovery_before_new_work",
})


def accepts_platform_jobs(linux: str | None, windows: str | None) -> bool:
    """GitHub needs.<job>.result must be exactly success for BOTH named jobs."""
    return linux == "success" and windows == "success"


def _ids(suite: unittest.TestSuite) -> set[str]:
    ids: set[str] = set()
    def visit(group: unittest.TestSuite) -> None:
        for item in group:
            if isinstance(item, unittest.TestSuite):
                visit(item)
            else:
                ids.add(item.id())
    visit(suite)
    return ids


def qualifies_tests(result: unittest.TestResult, discovered: set[str]) -> bool:
    """No test capability is silently qualified from a skipped test."""
    return (
        len(discovered) >= BASELINE_MINIMUM
        and REQUIRED_TEST_IDS <= discovered
        and result.testsRun >= BASELINE_MINIMUM
        and result.wasSuccessful()
        and not result.skipped
        and not result.expectedFailures
        and not result.unexpectedSuccesses
    )


def run_suite() -> int:
    suite = unittest.TestLoader().discover(start_dir="tests", pattern="test_*.py")
    ids = _ids(suite)
    if len(ids) < BASELINE_MINIMUM or not REQUIRED_TEST_IDS <= ids:
        missing = sorted(REQUIRED_TEST_IDS - ids)
        print(json.dumps({"qualified": False, "reason": "test-inventory-changed",
                          "count": len(ids), "missing": missing}, sort_keys=True))
        return 1
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    qualified = qualifies_tests(result, ids)
    print(json.dumps({"qualified": qualified, "discovered": len(ids),
                      "executed": result.testsRun, "skipped": len(result.skipped),
                      "expectedFailures": len(result.expectedFailures),
                      "unexpectedSuccesses": len(result.unexpectedSuccesses),
                      "errors": len(result.errors), "failures": len(result.failures)},
                     sort_keys=True))
    return 0 if qualified else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CI-13 mandatory acceptance predicates")
    commands = parser.add_subparsers(dest="mode", required=True)
    commands.add_parser("run-suite", help="all required tests must execute with zero skips")
    check = commands.add_parser("check-jobs", help="reject any non-success prerequisite")
    check.add_argument("--linux", default=None)
    check.add_argument("--windows", default=None)
    args = parser.parse_args(argv)
    if args.mode == "run-suite":
        return run_suite()
    qualified = accepts_platform_jobs(args.linux, args.windows)
    print(json.dumps({"qualified": qualified, "linux": args.linux, "windows": args.windows},
                     sort_keys=True))
    return 0 if qualified else 1


if __name__ == "__main__":
    sys.exit(main())
