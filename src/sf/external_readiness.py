"""PQ-07J: external custody/operational decision inventory (not authority).

A digest-pinned document may declare intended owners, never authenticate them.
There is deliberately no 'approved' state accepted from candidate JSON.
"""
from __future__ import annotations

import hashlib
import hmac
import json

from pathlib import Path

from .campaign_intake import GIT, HASH, IDENT, _safe_path, _read, _unique

REQUIRED_DECISIONS = (
    "publisher-trust-root-and-verifier",
    "signed-publisher-workflow-identity",
    "independent-protected-provider-ci",
    "grant-issuer-revocation-replay",
    "immutable-artifact-provenance-custody",
    "real-recovery-restore-and-target-fence",
    "authorized-disposable-linux-target",
    "authenticated-live-operator-incidents",
)
FIELDS = {"schemaVersion", "kind", "sourceCommit", "sourceTree",
          "artifactSha256", "profile", "decisions"}
PROFILE = {"scopeId", "platform", "adapter", "environment"}
DECISION = {"decisionId", "custodianLabel", "evidenceLocationId", "state"}
MAX_BYTES = 64 * 1024


class ExternalReadinessError(ValueError):
    """External decision declaration is incomplete or contradicted."""


def _expect(value, pattern, label):
    if type(value) is not str or pattern.fullmatch(value) is None:
        raise ExternalReadinessError("invalid " + label)


def inspect_external_decisions(
    manifest_path: Path, *, expected_manifest_sha256: str,
    expected_source_commit: str, expected_source_tree: str,
    expected_artifact_sha256: str,
) -> dict:
    """Read operator-created declarations without ever accepting authorization."""
    for value, pattern, label in (
        (expected_manifest_sha256, HASH, "manifest digest"),
        (expected_source_commit, GIT, "source commit"),
        (expected_source_tree, GIT, "source tree"),
        (expected_artifact_sha256, HASH, "artifact digest"),
    ):
        _expect(value, pattern, label)
    try:
        evidence = _read(_safe_path(str(manifest_path)), MAX_BYTES)
    except (ValueError, OSError) as exc:
        raise ExternalReadinessError("unavailable or unsafe decision document") from exc
    if evidence is None:
        raise ExternalReadinessError("decision document absent")
    raw, _identity = evidence
    if not hmac.compare_digest(hashlib.sha256(raw).hexdigest(), expected_manifest_sha256):
        raise ExternalReadinessError("decision manifest digest changed")
    try:
        manifest = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ExternalReadinessError("invalid decision manifest") from exc
    canonical = (json.dumps(manifest, sort_keys=True, ensure_ascii=True,
                            allow_nan=False, separators=(",", ":")) + "\n").encode()
    if type(manifest) is not dict or set(manifest) != FIELDS or raw != canonical:
        raise ExternalReadinessError("unsupported or noncanonical decision manifest")
    if (type(manifest["schemaVersion"]) is not int or manifest["schemaVersion"] != 1
            or manifest["kind"] != "sf-pq07j-external-decision-inventory"):
        raise ExternalReadinessError("unsupported decision manifest version")
    if (manifest["sourceCommit"], manifest["sourceTree"],
            manifest["artifactSha256"]) != (
            expected_source_commit, expected_source_tree,
            expected_artifact_sha256):
        raise ExternalReadinessError("decision scope mismatch")
    profile = manifest["profile"]
    if type(profile) is not dict or set(profile) != PROFILE:
        raise ExternalReadinessError("unsupported profile fields")
    for value in profile.values():
        _expect(value, IDENT, "profile identity")
    if (profile["platform"], profile["adapter"], profile["environment"]) != (
            "linux", "disposable-single-host", "test"):
        raise ExternalReadinessError("unqualified target profile")
    decisions = manifest["decisions"]
    if type(decisions) is not list or len(decisions) > len(REQUIRED_DECISIONS):
        raise ExternalReadinessError("invalid decision inventory")
    present = {}
    for item in decisions:
        if type(item) is not dict or set(item) != DECISION:
            raise ExternalReadinessError("unsupported decision fields")
        key = item["decisionId"]
        if type(key) is not str or key not in REQUIRED_DECISIONS or key in present:
            raise ExternalReadinessError("duplicate or unknown decision")
        _expect(item["custodianLabel"], IDENT, "custodian")
        _expect(item["evidenceLocationId"], IDENT, "evidence location")
        if type(item["state"]) is not str or item["state"] not in (
                "proposed", "pending", "blocked"):
            raise ExternalReadinessError("source document cannot assert approval")
        present[key] = item
    rows = [
        {"decisionId": key,
         "state": present[key]["state"] if key in present else "missing",
         "custodyAuthenticated": False}
        for key in REQUIRED_DECISIONS
    ]
    return {
        "schemaVersion": 1, "kind": "sf-pq07j-external-readiness-no-go",
        "sourceCommit": expected_source_commit,
        "sourceTree": expected_source_tree,
        "artifactSha256": expected_artifact_sha256,
        "manifestSha256": expected_manifest_sha256,
        "allDecisionsDeclared": len(present) == len(REQUIRED_DECISIONS),
        "decisionStates": rows,
        "custodyAuthenticated": False,
        "externalEffectsAuthorized": False,
        "productionQualified": False,
        "publishAuthorized": False,
        "adopterPilotAuthorized": False,
        "status": "BLOCKED-external-trust-and-live-evidence",
    }
