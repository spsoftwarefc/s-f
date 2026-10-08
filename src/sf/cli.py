"""Deterministic offline-first command entrypoint."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from . import __version__
from .profile import ProfileError, read_profile


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sf")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="inspect the installed CLI only")
    profile = sub.add_parser("profile", help="profile contract operations")
    ops = profile.add_subparsers(dest="operation", required=True)
    validate = ops.add_parser("validate")
    validate.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            print(json.dumps({"cliVersion": __version__, "offline": True, "releaseQualified": False}, sort_keys=True))
            return 0
        if args.command == "profile" and args.operation == "validate":
            read_profile(args.path)
            print(json.dumps({"valid": True, "schemaVersion": 1}, sort_keys=True))
            return 0
        return 2
    except (ProfileError, OSError) as exc:
        print(f"sf: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
