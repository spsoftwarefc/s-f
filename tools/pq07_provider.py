"""PQ-07O: operator-pinned, read-only live provider CI observer.

A successful invocation is NOT a release grant or checkout attestation.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sf.ci_evidence import EvidenceBlocked, EvidenceError, ProviderUnavailable
from sf.release_authority import AuthorityError, observe_pinned_ci


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Review GitHub provider CI against an out-of-band SHA-256 pinned policy")
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--policy-sha256", required=True,
                        help="64-character digest independently supplied by trusted operator")
    args = parser.parse_args(argv)
    try:
        value = observe_pinned_ci(args.policy, args.policy_sha256)
        if (type(value) is not dict or value.get("providerMetadataVerified") is not True
                or value.get("independentPolicyDigestMatched") is not True
                or value.get("independentPolicyCustodyVerified") is not False
                or value.get("effectAuthorized") is not False
                or value.get("accepted") is not False):
            raise AuthorityError("provider observation asserted unsupported authority")
    except (AuthorityError, EvidenceBlocked, EvidenceError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": type(exc).__name__,
                          "effectAuthorized": False, "accepted": False}, sort_keys=True))
        return 2
    except ProviderUnavailable:
        print(json.dumps({"status": "UNAVAILABLE", "effectAuthorized": False,
                          "accepted": False}, sort_keys=True))
        return 3
    print(json.dumps({"schemaVersion": 1, "kind": "sf-pq07o-read-only-provider-review",
                      "observation": value, "productionQualified": False,
                      "effectAuthorized": False, "accepted": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
