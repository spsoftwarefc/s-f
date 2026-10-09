"""PQ-07F: fail-closed cross-package *offline* readiness synthesis.

No caller-origin report or reference fixture is a release/deployment grant.
This function must never return an accepted production qualification.
"""
from __future__ import annotations

import re

from .production_dossier import REQUIRED_CLAIMS

SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SHA64 = re.compile(r"[0-9a-f]{64}\Z")

EXTERNAL_BLOCKERS = (
    "independent-publisher-trust-and-genuine-signature",
    "protected-provider-CI-checkout-and-artifact-identity",
    "authenticated-effect-grant-revocation-and-replay-store",
    "independently-retained-signed-build-and-SBOM-provenance",
    "real-kill-restore-and-remote-target-fencing-qualification",
    "authorized-Linux-service-migration-health-and-compensation",
    "authenticated-live-incident-and-operator-recovery-evidence",
    "independent-qualification-and-publication-authorization",
    "SF-R10-shared-agent-budget-unmet",
)


class PreflightError(ValueError):
    """Contradictory input, wrong source identity or unqualified scope."""


def _kind(data: dict, expected: str) -> dict:
    if type(data) is not dict or data.get("kind") != expected or (
            type(data.get("schemaVersion")) is not int or data["schemaVersion"] != 1):
        raise PreflightError("invalid cross-package report kind")
    return data


def _flag_false(data: dict, *fields: str) -> None:
    if any(data.get(field) is not False for field in fields):
        raise PreflightError("candidate evidence asserts unsupported external authority")


def _states(rows: object, label: str) -> bool:
    if type(rows) is not list or len(rows) != len(REQUIRED_CLAIMS):
        raise PreflightError("incomplete " + label + " claim oracle")
    for item, claim in zip(rows, REQUIRED_CLAIMS):
        if type(item) is not dict or set(item) != {"claim", "state"} or (
                item["claim"] != claim or type(item["state"]) is not str
                or item["state"] not in (
                    "missing", "failed", "unavailable", "identity-rejected",
                    "unsupported-profile", "present-unverified")):
            raise PreflightError("malformed " + label + " claim observation")
    return all(r["state"] == "present-unverified" for r in rows)


def assess_preflight(
    dossier: dict, policy: dict, audit: dict, registry: dict,
    recovery: dict, *, expected_source_commit: str,
    expected_source_tree: str, expected_artifact_sha256: str,
    expected_policy_sha256: str,
) -> dict:
    for name, value, pattern in (
        ("source commit", expected_source_commit, SHA40),
        ("source tree", expected_source_tree, SHA40),
        ("artifact", expected_artifact_sha256, SHA64),
        ("policy", expected_policy_sha256, SHA64),
    ):
        if type(value) is not str or pattern.fullmatch(value) is None:
            raise PreflightError("invalid expected " + name)
    _kind(dossier, "sf-pq07a-dossier-gap-report")
    _kind(policy, "sf-pq07b-policy-scope-observation")
    _kind(audit, "sf-pq07d-retained-byte-audit")
    _kind(registry, "sf-pq07e-local-evidence-coverage")
    _kind(recovery, "sf-pq07c-recovery-assessment")
    _flag_false(dossier, "accepted", "productionQualified",
                "externalIssuerAuthenticityVerified",
                "providerAndTargetEvidenceIndependentlyVerified")
    _flag_false(policy, "accepted", "productionQualified",
                "releaseAuthorized", "externalClaimsVerified",
                "independentPolicyCustodyVerified")
    _flag_false(audit, "accepted", "productionQualified",
                "releaseQualified", "signedProvenanceVerified",
                "independentPublisherCustodyVerified")
    _flag_false(registry, "accepted", "productionQualified",
                "independentAnchorVerified", "producerAuthenticityVerified")
    _flag_false(recovery, "retryAuthorized", "productionQualified",
                "targetReceiptAuthenticated", "remoteFenceQualified")
    candidate = dossier.get("candidate")
    if type(candidate) is not dict or (
            candidate.get("sourceCommit"),
            candidate.get("sourceTree"),
            candidate.get("artifactSha256")) != (
            expected_source_commit, expected_source_tree, expected_artifact_sha256):
        raise PreflightError("candidate commit/tree/artifact mismatch")
    if (registry.get("sourceCommit"), registry.get("artifactSha256"),
            audit.get("artifactSha256"), policy.get("policySha256")) != (
            expected_source_commit, expected_artifact_sha256,
            expected_artifact_sha256, expected_policy_sha256):
        raise PreflightError("cross-package digest mismatch")
    if (policy.get("sourceScopeMatched") is not True
            or dossier.get("scopeSupportedForReference") is not True
            or audit.get("bytesRechecked") is not True):
        raise PreflightError("unsupported reference scope or absent byte proof")
    if recovery.get("localClassification") not in (
            "INTENT_ONLY", "UNKNOWN_EFFECT", "REFERENCE_EFFECT_PRESENT_UNVERIFIED"):
        raise PreflightError("contradictory or unsupported recovery result")
    dossier_complete = _states(dossier.get("claimStates"), "dossier")
    registry_complete = _states(registry.get("claimStates"), "registry")
    return {
        "schemaVersion": 1,
        "kind": "sf-pq07f-production-preflight-no-go",
        "sourceCommit": expected_source_commit,
        "sourceTree": expected_source_tree,
        "artifactSha256": expected_artifact_sha256,
        "policySha256": expected_policy_sha256,
        "referenceLocalRecordsPresent": dossier_complete and registry_complete,
        "externalQualificationBlockers": list(EXTERNAL_BLOCKERS),
        "publisherAuthenticated": False,
        "deploymentQualified": False,
        "liveOperationsQualified": False,
        "releaseAuthorized": False,
        "publishAuthorized": False,
        "adopterPilotAuthorized": False,
        "SF_R10": "UNMET-overall",
        "accepted": False, "productionQualified": False,
        "status": "BLOCKED-external-qualification",
    }
