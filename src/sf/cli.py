"""Deterministic offline-first command entrypoint."""
from __future__ import annotations

import argparse
import json
import signal
import sys
import threading
from pathlib import Path

from . import __version__
from .ci_evidence import (EvidenceError, EvidenceBlocked, ProviderUnavailable,
                          read_request, verify_github, inspect_offline)
from .assurance import AssuranceError, read_packet, inspect_review
from .security import SecurityError, read_policy, assess_security
from .distribution import DistributionError, build_bundle, verify_bundle
from .adapters import declared_check_plan
from .execution import ExecutionError, execute_check
from .inventory import InventoryError, inventory
from .integration import IntegrationError, plan_install
from .lifecycle import execute_plan, plan_lifecycle, recover
from .profile import ProfileError, read_profile
from .work import WorkError, inspect_work


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sf")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="inspect the installed CLI only")
    inv = sub.add_parser("inventory", help="read-only repository discovery")
    inv.add_argument("path", type=Path)
    profile = sub.add_parser("profile", help="profile contract operations (never executes checks)")
    ops = profile.add_subparsers(dest="operation", required=True)
    for operation in ("validate", "plan"):
        command = ops.add_parser(operation)
        command.add_argument("path", type=Path)
        command.add_argument("--root", type=Path, default=None,
                             help="optionally verify declared directories in this project root")
    for operation in ("integrate", "upgrade", "remove"):
        command = sub.add_parser(operation, help="explicit, checked factory lifecycle operation")
        effect = command.add_mutually_exclusive_group(required=True)
        effect.add_argument("--dry-run", action="store_true", help="inspect proposed changes")
        effect.add_argument("--apply", type=Path, metavar="PLAN", help="apply an exact saved plan")
        command.add_argument("--root", type=Path, required=True)
        if operation != "remove":
            command.add_argument("--profile", type=Path, required=True)
        if operation == "integrate":
            command.add_argument("--ack-manual-routing", action="store_true",
                                 help="preserve existing AGENTS.md and acknowledge manual routing")
    recovery = sub.add_parser("recover", help="verify and resume an interrupted factory transaction")
    recovery.add_argument("--root", type=Path, required=True)
    work = sub.add_parser("work", help="read-only work-order assessment")
    work_ops = work.add_subparsers(dest="operation", required=True)
    for operation in ("start", "resume"):
        command = work_ops.add_parser(operation)
        command.add_argument("--root", type=Path, required=True)
        command.add_argument("--order", required=True, help="committed repository-relative JSON work-order path")
        command.add_argument("--base-ref", default=None, help="optional local integration branch for drift detection")
    run = sub.add_parser("run", help="execute one explicitly declared local project check")
    run.add_argument("check_id", help="exact command identifier declared in project profile")
    run.add_argument("--root", type=Path, required=True)
    run.add_argument("--profile", required=True, help="repository-relative project profile path")
    run.add_argument("--receipt-out", default=None, help="existing-parent, new repository-relative receipt file")
    run.add_argument("--allow-network", action="store_true", help="acknowledge network-capable declared command")
    run.add_argument("--redact-env", action="append", default=[], metavar="NAME",
                     help="redact a sensitive value from the named environment variable (repeatable)")
    evidence = sub.add_parser("evidence", help="explicit CI evidence verification")
    evidence_ops = evidence.add_subparsers(dest="operation", required=True)
    verify = evidence_ops.add_parser("verify", help="check provider metadata or mark offline snapshot unverified")
    verify.add_argument("--request", type=Path, required=True, help="versioned source/CI job expectation JSON")
    verify.add_argument("--source", choices=("github", "offline"), required=True)
    verify.add_argument("--snapshot", type=Path, default=None, help="offline-only local JSON snapshot")
    for name in ("review", "readiness"):
        assessment = sub.add_parser(name, help="source-bound offline assurance assessment (no acceptance authority)")
        assessment.add_argument("--root", type=Path, required=True)
        assessment.add_argument("--packet", type=Path, required=True)
    security = sub.add_parser("security", help="explicit read-only security and dependency observations")
    security_ops = security.add_subparsers(dest="operation", required=True)
    sec = security_ops.add_parser("assess", help="assess tracked files and source-bound scanner snapshots")
    sec.add_argument("--root", type=Path, required=True)
    sec.add_argument("--policy", type=Path, required=True)
    dist = sub.add_parser("distribution", help="offline deterministic factory distribution (no publication)")
    dist_ops = dist.add_subparsers(dest="operation", required=True)
    build = dist_ops.add_parser("build", help="build clean committed factory bundle")
    build.add_argument("--root", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--publisher", required=True)
    build.add_argument("--release-id", required=True)
    release_verify = dist_ops.add_parser("verify", help="check bundle against independently supplied trust pin")
    release_verify.add_argument("--bundle", type=Path, required=True)
    release_verify.add_argument("--trust", type=Path, required=True)
    release_verify.add_argument("--lock-out", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        if args.command == "distribution":
            if args.operation == "build":
                result = build_bundle(args.root, args.output, publisher=args.publisher, release_id=args.release_id)
            else:
                result = verify_bundle(args.bundle, args.trust, lock_out=args.lock_out)
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            return 0
        if args.command == "security":
            result = assess_security(args.root, read_policy(args.policy))
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            return 1 if result["status"] != "observed-clear-not-certified" else 0
        if args.command in ("review", "readiness"):
            result = inspect_review(args.root, read_packet(args.packet), summary=args.command == "readiness")
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            return 1 if result["blockers"] else 0
        if args.command == "evidence":
            request = read_request(args.request)
            if args.source == "github":
                if args.snapshot is not None:
                    raise EvidenceError("--snapshot is only valid with --source offline")
                result = verify_github(request)
                print(json.dumps(result, ensure_ascii=False, sort_keys=True))
                return 0
            if args.snapshot is None:
                raise EvidenceError("--source offline requires --snapshot")
            result = inspect_offline(request, args.snapshot)
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            return 1  # inspection is not provider verification
        if args.command == "run":
            cancel = threading.Event()
            previous = {}
            if threading.current_thread() is threading.main_thread():
                for kind in (signal.SIGINT, signal.SIGTERM):
                    previous[kind] = signal.getsignal(kind)
                    signal.signal(kind, lambda _sig, _frame: cancel.set())
            try:
                receipt = execute_check(args.root, args.profile, args.check_id,
                                        receipt_out=args.receipt_out, allow_network=args.allow_network,
                                        redact_env=args.redact_env, cancel_event=cancel)
            finally:
                for kind, handler in previous.items():
                    signal.signal(kind, handler)
            print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
            return 0 if receipt["result"]["outcome"] == "success" else 1
        if args.command == "work":
            assessment = inspect_work(args.root, args.order, mode=args.operation,
                                      base_ref=args.base_ref)
            print(json.dumps(assessment, ensure_ascii=False, sort_keys=True))
            return 1 if assessment["blockers"] else 0
        if args.command == "inventory":
            print(json.dumps(inventory(args.path), sort_keys=True))
            return 0
        if args.command == "doctor":
            print(json.dumps({"cliVersion": __version__, "offline": True,
                              "releaseQualified": False}, sort_keys=True))
            return 0
        if args.command == "recover":
            print(json.dumps(recover(args.root), ensure_ascii=False, sort_keys=True))
            return 0
        if args.command in ("integrate", "upgrade", "remove"):
            target_profile = args.profile if args.command != "remove" else None
            acknowledgement = getattr(args, "ack_manual_routing", False)
            if args.dry_run:
                plan = plan_lifecycle(args.command, args.root, target_profile,
                                      ack_manual=acknowledgement)
                print(json.dumps(plan, ensure_ascii=False, sort_keys=True))
                return 1 if plan["conflicts"] else 0
            receipt = execute_plan(args.root, target_profile, args.apply, mode=args.command,
                                   ack_manual=acknowledgement)
            print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
            return 0
        if args.command == "profile":
            data = read_profile(args.path, root=args.root)
            if args.operation == "validate":
                print(json.dumps({"valid": True, "schemaVersion": 1,
                                  "pathsVerified": args.root is not None,
                                  "releaseQualified": False}, sort_keys=True))
            elif args.operation == "plan":
                print(json.dumps(declared_check_plan(data), sort_keys=True))
            return 0
        return 2
    except EvidenceBlocked as exc:
        print(json.dumps({"schemaVersion": 1, "status": "blocked", "providerMetadataVerified": False,
                          "accepted": False, "reason": str(exc)}, sort_keys=True))
        return 1
    except ProviderUnavailable:
        print(json.dumps({"schemaVersion": 1, "status": "unknown", "providerMetadataVerified": False,
                          "accepted": False, "reason": "provider-unavailable-or-incomplete"}, sort_keys=True))
        return 2
    except (DistributionError, SecurityError, AssuranceError, EvidenceError, ExecutionError, WorkError, ProfileError, InventoryError,
            IntegrationError, OSError, RecursionError) as exc:
        print(f"sf: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
