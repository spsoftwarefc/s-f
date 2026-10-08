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
from .profile import ProfileError, read_profile


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
    integration = sub.add_parser("integrate", help="plan repository integration without writes")
    integration.add_argument("--dry-run", action="store_true", required=True,
                             help="the only supported SF-05 integration mode")
    integration.add_argument("--root", type=Path, required=True)
    integration.add_argument("--profile", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "inventory":
            print(json.dumps(inventory(args.path), sort_keys=True))
            return 0
        if args.command == "doctor":
            print(json.dumps({"cliVersion": __version__, "offline": True,
                              "releaseQualified": False}, sort_keys=True))
            return 0
        if args.command == "integrate":
            plan = plan_install(args.root, args.profile)
            print(json.dumps(plan, ensure_ascii=False, sort_keys=True))
            return 1 if plan["conflicts"] else 0
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
    except (ProfileError, InventoryError, IntegrationError, OSError, RecursionError) as exc:
        print(f"sf: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
