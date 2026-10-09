"""PQ-07T: read-only, operator-digest-pinned live campaign intake.

An independently supplied checksum and syntax do NOT authenticate a custodian.
No result of this module grants any release, deployment or publication authority.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .campaign_intake import GIT, HASH, IDENT, _read, _safe_path, _unique
from .external_readiness import REQUIRED_DECISIONS

MAX_MANIFEST = 128 * 1024
FIELDS = {"schemaVersion", "kind", "sourceCommit", "sourceTree", "artifactSha256",
          "policySha256", "profile", "preparedAt", "expiresAt", "externalDecisions"}
PROFILE = {"scopeId", "platform", "adapter", "environment"}
DECISION = {"decisionId", "referenceSha256", "state"}
UTC_TIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")


class LiveCampaignIntakeError(ValueError):
    """Invalid, expired or unsupported candidate-origin campaign manifest."""


def _utc(value: object) -> datetime:
    if type(value) is not str or UTC_TIME.fullmatch(value) is None:
        raise LiveCampaignIntakeError("invalid canonical UTC timestamp")
    try:
        dt = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise LiveCampaignIntakeError("invalid calendar timestamp") from exc
    return dt.replace(tzinfo=timezone.utc)


def _expect_digest(value: object, pattern: re.Pattern[str], name: str) -> None:
    if type(value) is not str or pattern.fullmatch(value) is None:
        raise LiveCampaignIntakeError("invalid " + name)


def inspect_live_campaign(
    manifest_path: Path, *, expected_manifest_sha256: str,
    expected_source_commit: str, expected_source_tree: str,
    expected_artifact_sha256: str, expected_policy_sha256: str,
    now: datetime | None = None,
) -> dict:
    """Check exact file and independent caller pins without accepting self-approval."""
    for value, pattern, label in (
        (expected_manifest_sha256, HASH, "manifest pin"),
        (expected_source_commit, GIT, "source commit"),
        (expected_source_tree, GIT, "source tree"),
        (expected_artifact_sha256, HASH, "artifact pin"),
        (expected_policy_sha256, HASH, "policy pin"),
    ):
        _expect_digest(value, pattern, label)
    try:
        read = _read(_safe_path(str(manifest_path)), MAX_MANIFEST)
    except (OSError, ValueError) as exc:
        raise LiveCampaignIntakeError("unsafe or unavailable manifest") from exc
    if read is None:
        raise LiveCampaignIntakeError("campaign manifest missing")
    raw, _ = read
    if not hmac.compare_digest(hashlib.sha256(raw).hexdigest(), expected_manifest_sha256):
        raise LiveCampaignIntakeError("operator manifest pin mismatch")
    try:
        document = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise LiveCampaignIntakeError("invalid campaign manifest JSON") from exc
    canonical = (json.dumps(document, sort_keys=True, ensure_ascii=True,
                            allow_nan=False, separators=(",", ":")) + "\n").encode()
    if type(document) is not dict or set(document) != FIELDS or canonical != raw:
        raise LiveCampaignIntakeError("noncanonical or unauthorized manifest fields")
    if (type(document["schemaVersion"]) is not int or document["schemaVersion"] != 1
            or document["kind"] != "sf-pq07t-live-campaign-intake"):
        raise LiveCampaignIntakeError("unsupported campaign schema")
    for key, expected in (
        ("sourceCommit", expected_source_commit),
        ("sourceTree", expected_source_tree),
        ("artifactSha256", expected_artifact_sha256),
        ("policySha256", expected_policy_sha256),
    ):
        if document[key] != expected:
            raise LiveCampaignIntakeError("campaign pin or scope mismatch")
    profile = document["profile"]
    if type(profile) is not dict or set(profile) != PROFILE:
        raise LiveCampaignIntakeError("unsupported campaign profile")
    for key in PROFILE:
        _expect_digest(profile[key], IDENT, "profile " + key)
    if (profile["platform"], profile["adapter"], profile["environment"]) != (
            "linux", "disposable-single-host", "test"):
        raise LiveCampaignIntakeError("unsupported live campaign environment")
    clock = now if now is not None else datetime.now(timezone.utc)
    if type(clock) is not datetime or clock.tzinfo is None:
        raise LiveCampaignIntakeError("UTC-aware observation clock required")
    clock = clock.astimezone(timezone.utc)
    start, expiry = _utc(document["preparedAt"]), _utc(document["expiresAt"])
    if not start <= clock <= expiry or expiry <= start or expiry - start > timedelta(days=1):
        raise LiveCampaignIntakeError("stale, future or excessive campaign window")
    items = document["externalDecisions"]
    if type(items) is not list or len(items) > len(REQUIRED_DECISIONS):
        raise LiveCampaignIntakeError("invalid external decision inventory")
    found = {}
    for item in items:
        if type(item) is not dict or set(item) != DECISION:
            raise LiveCampaignIntakeError("invalid external decision entry")
        key = item["decisionId"]
        if type(key) is not str or key not in REQUIRED_DECISIONS or key in found:
            raise LiveCampaignIntakeError("unknown or duplicated external decision")
        _expect_digest(item["referenceSha256"], HASH, "external reference digest")
        if type(item["state"]) is not str or item["state"] not in ("pending", "blocked"):
            raise LiveCampaignIntakeError("candidate must not assert approval")
        found[key] = item
    return {
        "schemaVersion": 1, "kind": "sf-pq07t-live-campaign-intake-no-go",
        "sourceCommit": expected_source_commit, "sourceTree": expected_source_tree,
        "artifactSha256": expected_artifact_sha256,
        "policySha256": expected_policy_sha256,
        "manifestSha256": expected_manifest_sha256,
        "profile": profile,
        "missingDecisionIds": [x for x in REQUIRED_DECISIONS if x not in found],
        "allDecisionsDeclared": len(found) == len(REQUIRED_DECISIONS),
        "independentCustodyVerified": False, "providerAuthenticated": False,
        "releaseAuthorized": False, "deploymentAuthorized": False,
        "publishAuthorized": False, "adopterPilotAuthorized": False,
        "productionQualified": False, "accepted": False,
        "SF_R10": "UNMET-overall", "status": "BLOCKED-external-qualification",
    }
