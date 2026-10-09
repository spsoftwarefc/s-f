"""PQ-07U: fail-closed read-only cross-boundary supply-chain observation join.

This consumes *already reviewed* inputs, and never accepts those source-side
observations as independent signing-policy custody or effect authorization.
"""
from __future__ import annotations

import re

GIT = re.compile(r"[0-9a-f]{40}\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")


class SupplyChainHandoffError(ValueError):
    """Read-only observations disagree or assert unauthorized production rights."""


def _identity(item: object, pattern: re.Pattern[str], label: str) -> str:
    if type(item) is not str or pattern.fullmatch(item) is None:
        raise SupplyChainHandoffError("invalid " + label)
    return item


def _false(data: dict, *fields: str) -> None:
    for field in fields:
        if data.get(field) is not False:
            raise SupplyChainHandoffError("unsupported or elevated authority: " + field)


def assess_supply_chain_handoff(
    intake: dict, retained: dict, provider: dict, *,
    expected_source_commit: str, expected_source_tree: str,
    expected_artifact_sha256: str, expected_policy_sha256: str,
) -> dict:
    """Bind three independent inspection *results*, not their actual custody."""
    for value, pattern, label in (
        (expected_source_commit, GIT, "source commit"),
        (expected_source_tree, GIT, "source tree"),
        (expected_artifact_sha256, HASH, "artifact digest"),
        (expected_policy_sha256, HASH, "policy digest"),
    ):
        _identity(value, pattern, label)
    if not all(type(item) is dict for item in (intake, retained, provider)):
        raise SupplyChainHandoffError("invalid observed report type")
    if (intake.get("kind") != "sf-pq07t-live-campaign-intake-no-go"
            or retained.get("kind") != "sf-pq07p-retained-publisher-no-go"
            or provider.get("kind") != "sf-ci-provider-metadata-observation"):
        raise SupplyChainHandoffError("missing expected independent review stage")
    for record in (intake, retained):
        for field, expected in (("sourceCommit", expected_source_commit),
                                ("sourceTree", expected_source_tree),
                                ("artifactSha256", expected_artifact_sha256),
                                ("policySha256", expected_policy_sha256)):
            if record.get(field) != expected:
                raise SupplyChainHandoffError("cross-boundary " + field + " mismatch")
    _false(intake, "independentCustodyVerified", "providerAuthenticated",
           "releaseAuthorized", "deploymentAuthorized",
           "publishAuthorized", "adopterPilotAuthorized", "productionQualified",
           "accepted")
    if intake.get("status") != "BLOCKED-external-qualification":
        raise SupplyChainHandoffError("campaign intake claims qualification")
    if (retained.get("exactRetainedBytesObserved") is not True
            or retained.get("status") != "BLOCKED-external-qualification"):
        raise SupplyChainHandoffError("missing retained-byte reviewer evidence")
    _false(retained, "independentRetentionCustodyVerified",
           "independentPolicyCustodyVerified", "installationAuthorized",
           "releaseQualified", "productionQualified", "accepted")
    if (provider.get("source") != "github"
            or provider.get("event") != "merge_group"
            or provider.get("candidateSha") != expected_source_commit
            or provider.get("status") != "provider-metadata-verified"
            or provider.get("providerMetadataVerified") is not True
            or provider.get("independentPolicyDigestMatched") is not True
            or provider.get("checkoutSha") != "unknown"
            or provider.get("artifactBytesVerified") is not False):
        raise SupplyChainHandoffError("provider observation insufficient or wrong candidate")
    _false(provider, "independentPolicyVerified",
           "independentPolicyCustodyVerified", "effectAuthorized", "accepted")
    if type(provider.get("runId")) is not int or provider["runId"] <= 0:
        raise SupplyChainHandoffError("missing provider run ID")
    if type(provider.get("attempt")) is not int or provider["attempt"] <= 0:
        raise SupplyChainHandoffError("missing provider attempt")
    return {
        "schemaVersion": 1, "kind": "sf-pq07u-supply-chain-handoff-no-go",
        "sourceCommit": expected_source_commit, "sourceTree": expected_source_tree,
        "artifactSha256": expected_artifact_sha256,
        "policySha256": expected_policy_sha256,
        "providerRunId": provider["runId"], "providerAttempt": provider["attempt"],
        "readOnlyObservationsConsistent": True,
        "artifactConsumedBytesRecheckedLocally": True,
        "externalPublisherCustodyAuthenticated": False,
        "providerCheckoutAuthenticated": False,
        "independentArtifactRetentionQualified": False,
        "effectGrantVerified": False, "releaseAuthorized": False,
        "deploymentAuthorized": False, "productionQualified": False,
        "publishAuthorized": False, "accepted": False,
        "status": "BLOCKED-external-qualification",
    }
