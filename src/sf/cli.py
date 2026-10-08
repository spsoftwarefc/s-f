"""Deterministic offline-first command entrypoint."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .adapters import declared_check_plan
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
    args = parser.parse_args(argv)
    try:
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
    except (WorkError, ProfileError, InventoryError, IntegrationError, OSError, RecursionError) as exc:
        print(f"sf: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
