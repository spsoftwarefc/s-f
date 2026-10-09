"""PQ-07W: strictly local, non-authoritative operations and evidence oracle."""
from __future__ import annotations

from .production_dossier import REQUIRED_CLAIMS
from .campaign_intake import GIT, IDENT

OPS_FIELDS = {"schemaVersion", "kind", "sourceCommit", "targetId",
              "observerIdentityDeclared", "openIncidents",
              "verifiedLiveTelemetry", "incidentOwnerAuthenticated",
              "operationsQualified", "accepted"}
CASE_FIELDS = {"claim", "positive", "negative"}


class LiveCampaignReviewError(ValueError):
    """Incomplete, contradictory or source-authorized cross-boundary evidence."""


def _false(report: dict, *names: str) -> None:
    for name in names:
        if report.get(name) is not False:
            raise LiveCampaignReviewError("unsupported qualified state: " + name)


def review_live_campaign(
    intake: dict, supply: dict, target: dict,
    recovery: dict, operations: dict, cases: list,
    *, expected_source_commit: str,
) -> dict:
    """Accept only consistent source observations; never live approval."""
    if (type(expected_source_commit) is not str
            or GIT.fullmatch(expected_source_commit) is None):
        raise LiveCampaignReviewError("invalid source identity")
    if not all(type(x) is dict for x in (intake, supply, target, recovery, operations)):
        raise LiveCampaignReviewError("missing structured source-side evidence")
    expected_kinds = (
        (intake, "sf-pq07t-live-campaign-intake-no-go"),
        (supply, "sf-pq07u-supply-chain-handoff-no-go"),
        (target, "sf-pq07v-reference-target-no-go"),
        (recovery, "sf-pq07q-local-reference-process-death"),
        (operations, "sf-pq07w-operator-incident-intake"),
    )
    for record, expected in expected_kinds:
        if record.get("kind") != expected:
            raise LiveCampaignReviewError("incorrect qualification evidence kind")
    for record in (intake, supply, target, operations):
        if record.get("sourceCommit") != expected_source_commit:
            raise LiveCampaignReviewError("cross-boundary source substitution")
    if (intake.get("artifactSha256") != supply.get("artifactSha256")
            or intake.get("artifactSha256") != target.get("artifactSha256")
            or intake.get("policySha256") != supply.get("policySha256")):
        raise LiveCampaignReviewError("cross-boundary artifact or policy substitution")
    _false(intake, "productionQualified", "accepted")
    if (supply.get("readOnlyObservationsConsistent") is not True
            or target.get("capabilitiesDeclared") is not True
            or recovery.get("localProcessExitObserved") is not True
            or recovery.get("localReceiptRecovered") is not True):
        raise LiveCampaignReviewError("missing local cross-package proof")
    _false(supply, "effectGrantVerified", "releaseAuthorized",
           "deploymentAuthorized", "productionQualified", "accepted")
    _false(target, "actualTargetOwnershipAuthenticated", "destinationCASVerified",
           "remoteReceiptAuthenticated", "liveFaultCasesExecuted",
           "liveRecoveryQualified", "externalEffectAuthorized",
           "productionQualified", "accepted")
    _false(recovery, "realRemoteFenceQualified", "realServiceDeployed",
           "liveOperationsVerified", "productionQualified")
    if (set(operations) != OPS_FIELDS
            or type(operations["schemaVersion"]) is not int
            or operations["schemaVersion"] != 1
            or operations["targetId"] != target.get("targetId")
            or operations["observerIdentityDeclared"] is not True):
        raise LiveCampaignReviewError("unsupported operator incident intake")
    _false(operations, "verifiedLiveTelemetry", "incidentOwnerAuthenticated",
           "operationsQualified", "accepted")
    incidents = operations["openIncidents"]
    if (type(incidents) is not list or len(incidents) > 128
            or any(type(x) is not str or IDENT.fullmatch(x) is None
                   for x in incidents)
            or len(set(incidents)) != len(incidents)):
        raise LiveCampaignReviewError("invalid unresolved incident identifiers")
    if type(cases) is not list or len(cases) != len(REQUIRED_CLAIMS):
        raise LiveCampaignReviewError("incomplete qualification evidence oracle")
    for row, key in zip(cases, REQUIRED_CLAIMS):
        if (type(row) is not dict or set(row) != CASE_FIELDS
                or row.get("claim") != key
                or row.get("positive") not in ("present-unverified", "missing")
                or row.get("negative") not in ("present-unverified", "missing")):
            raise LiveCampaignReviewError("forged or incorrect campaign claim")
    return {
        "schemaVersion": 1, "kind": "sf-pq07w-live-operations-no-go",
        "sourceCommit": expected_source_commit,
        "targetId": target["targetId"],
        "claimCasesPresentUnverified": all(
            r["positive"] == r["negative"] == "present-unverified" for r in cases),
        "unresolvedIncidentCount": len(incidents),
        "independentlyAuthenticatedOperations": False,
        "independentlyQualifiedPublisher": False,
        "independentlyQualifiedDeployment": False,
        "releaseAuthorized": False, "publishAuthorized": False,
        "productionQualified": False, "adopterPilotAuthorized": False,
        "SF_R10": "UNMET-overall", "accepted": False,
        "status": "BLOCKED-external-qualification",
    }
