"""PQ-07V: disposable Linux *declaration* preflight, not remote target proof.

No network access or credentials: a candidate document cannot authorize itself.
"""
from __future__ import annotations

import re

GIT = re.compile(r"[0-9a-f]{40}\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")
IDENT = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,127}\Z")
FIELDS = {"schemaVersion", "kind", "sourceCommit", "sourceTree",
          "artifactSha256", "ownerId", "targetId", "platform", "environment",
          "disposable", "backend", "capabilities", "limits", "faultCases"}
CAPABILITIES = {"destinationAtomicCAS", "destinationIdempotency",
                "authenticatedStatus", "rollbackBoundaryDeclared"}
LIMITS = {"maxMemoryMiB", "maxDiskMiB", "maxDurationSeconds"}
FAULTS = (
    "intent-before-effect", "kill-before-dispatch", "lost-reply",
    "kill-after-remote-cas", "stale-worker-fence", "duplicate-operation",
    "sqlite-contention", "stale-backup-restore", "partial-migration",
    "failed-health", "ambiguous-compensation", "restart-open-incident",
)


class TargetContractError(ValueError):
    """Invalid or unsupported proposed disposable live qualification target."""


def _id(value: object, pattern: re.Pattern[str]) -> None:
    if type(value) is not str or pattern.fullmatch(value) is None:
        raise TargetContractError("invalid target identity")


def inspect_target_contract(
    contract: dict, *, expected_source_commit: str,
    expected_source_tree: str, expected_artifact_sha256: str,
) -> dict:
    """Return scoped missing-live-evidence report, never an effect handle."""
    for value, pattern in ((expected_source_commit, GIT),
                           (expected_source_tree, GIT),
                           (expected_artifact_sha256, HASH)):
        _id(value, pattern)
    if type(contract) is not dict or set(contract) != FIELDS:
        raise TargetContractError("unknown or missing target declaration fields")
    if (type(contract["schemaVersion"]) is not int
            or contract["schemaVersion"] != 1
            or contract["kind"] != "sf-pq07v-proposed-reference-target"):
        raise TargetContractError("invalid proposed target contract version")
    for key, expected in (("sourceCommit", expected_source_commit),
                          ("sourceTree", expected_source_tree),
                          ("artifactSha256", expected_artifact_sha256)):
        if contract[key] != expected:
            raise TargetContractError("target candidate mismatch")
    for key in ("ownerId", "targetId"):
        _id(contract[key], IDENT)
    if (contract["platform"] != "linux" or contract["environment"] != "test"
            or contract["backend"] != "disposable-single-host"
            or contract["disposable"] is not True):
        raise TargetContractError("only isolated disposable Linux test targets supported")
    capabilities = contract["capabilities"]
    if type(capabilities) is not dict or set(capabilities) != CAPABILITIES:
        raise TargetContractError("unknown target capability contract")
    if not all(capabilities[name] is True for name in CAPABILITIES):
        raise TargetContractError("required target capability not declared")
    limits = contract["limits"]
    if type(limits) is not dict or set(limits) != LIMITS:
        raise TargetContractError("invalid qualification resource limits")
    bounds = {"maxMemoryMiB": (64, 4096), "maxDiskMiB": (32, 8192),
              "maxDurationSeconds": (60, 7200)}
    for name, (lower, upper) in bounds.items():
        number = limits[name]
        if type(number) is not int or not lower <= number <= upper:
            raise TargetContractError("unsupported live test resource bound")
    cases = contract["faultCases"]
    if type(cases) is not list or len(cases) != len(FAULTS):
        raise TargetContractError("incomplete fault matrix")
    if cases != [{"case": name, "state": "planned"} for name in FAULTS]:
        raise TargetContractError("unsupported fault matrix or preclaimed success")
    return {
        "schemaVersion": 1, "kind": "sf-pq07v-reference-target-no-go",
        "sourceCommit": expected_source_commit, "sourceTree": expected_source_tree,
        "artifactSha256": expected_artifact_sha256,
        "targetId": contract["targetId"],
        "faultCaseCount": len(FAULTS),
        "capabilitiesDeclared": True, "faultsPlanned": True,
        "actualTargetOwnershipAuthenticated": False,
        "destinationCASVerified": False, "remoteReceiptAuthenticated": False,
        "liveFaultCasesExecuted": False, "liveRecoveryQualified": False,
        "externalEffectAuthorized": False,
        "productionQualified": False, "accepted": False,
        "status": "BLOCKED-external-qualification",
    }
