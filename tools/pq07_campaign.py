"""PQ-07I: read-only local campaign evidence intake command.

Exit 0 means local assessment completed, NOT qualified or authorized.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Run from an uninstalled source checkout without modifying the user's project.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sf.campaign_intake import CampaignIntakeError, inspect_campaign


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inventory raw PQ-07 campaign proof bytes (always unqualified)"
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-tree", required=True)
    parser.add_argument("--artifact-sha256", required=True)
    parser.add_argument("--policy-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = inspect_campaign(
            args.manifest,
            expected_manifest_sha256=args.manifest_sha256,
            expected_source_commit=args.source_commit,
            expected_source_tree=args.source_tree,
            expected_artifact_sha256=args.artifact_sha256,
            expected_policy_sha256=args.policy_sha256,
        )
    except (CampaignIntakeError, OSError) as exc:
        print("PQ-07 local input rejected: " + str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
