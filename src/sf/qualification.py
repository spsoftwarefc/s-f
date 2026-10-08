"""SF-19: read-only, cross-package development factory qualification.

This is not authentication of a release, deployment authority, real health,
durable recovery, or approval to merge. Inputs outside the bundle/target are
caller-provided and may be forged; their semantics are checked, not attested.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from . import pinned
from .deployment import qualify_deployment, validate_release_plan
from .distribution import DistributionError
from .integration import IntegrationError, _observe
from .operations import assess_operations, OperationsError


class QualificationError(ValueError):
    """Candidate cannot demonstrate the required synthetic cross-package chain."""


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _clock(value: datetime | None) -> datetime:
    current = value if value is not None else datetime.now(timezone.utc)
    if (not isinstance(current, datetime) or current.tzinfo is None
            or current.utcoffset() != timedelta(0)):
        raise QualificationError("qualification clock must be UTC aware")
    return current.astimezone(timezone.utc)


def qualify_factory(target: Path, bundle: Path, trust: Path, lock: Path,
                    release_plan: dict, deployment_report: dict, policy: dict,
                    observations: dict, *, now: datetime | None = None) -> dict:
    """Verify installed owned bytes and recompute synthetic release/ops tests.

    No filesystem mutation, subprocess or network operations. The integrity of
    the caller's chosen trust pin and SF-14 release approval is outside scope.
    """
    current = _clock(now)
    if target.is_symlink() or not target.is_dir():
        raise QualificationError("target must be a real installation directory")
    try:
        verified_lock, members = pinned._verified_source(bundle, trust, lock)
        profile, route_owned, current_hashes, installed_record = pinned._installed(target)
        if installed_record["lock"] != verified_lock:
            raise QualificationError("installed factory source lock changed")
        expected_record = pinned._record(verified_lock, members)
        if installed_record != expected_record:
            raise QualificationError("installed factory archive member inventory changed")
        expected_files = pinned._new_files(profile, route_owned, verified_lock, members)
        if set(expected_files) != set(current_hashes):
            raise QualificationError("installed factory owned-path inventory mismatch")
        for path, raw in expected_files.items():
            observed = _observe(target, path)
            if observed != {"state": "file", "sha256": _digest(raw)}:
                raise QualificationError("installed factory owned member mismatch: " + path)
        if _observe(target, ".s-f-transaction.json")["state"] != "absent":
            raise QualificationError("unsettled installer transaction")
        release = validate_release_plan(release_plan)
        if (release["source"]["commit"] != verified_lock["sourceCommit"]
                or release["source"]["tree"] != verified_lock["sourceTree"]):
            raise QualificationError("release plan source differs from independently verified installed archive")
        if release["artifact"]["sha256"] != verified_lock["bundleSha256"]:
            raise QualificationError("release artifact differs from exact installed archive")
        # SF-15's source and target bindings are recomputed, not accepted from
        # a candidate-supplied claim. The fake-target result remains simulated.
        simulated = qualify_deployment(release, today=current.date())
        if deployment_report != simulated or not simulated["syntheticPassed"]:
            raise QualificationError("substituted, stale or failed SF-15 synthetic evidence")
        operations = assess_operations(deployment_report, policy, observations, now=current)
        if (operations["sourceCommit"] != release["source"]["commit"]
                or operations["planSha256"] != simulated["planSha256"]
                or operations["destination"] != release["destination"]):
            raise QualificationError("operations source/destination binding differs")
    except QualificationError:
        raise
    except (DistributionError, IntegrationError, OperationsError,
            ValueError, TypeError, KeyError, OSError) as exc:
        raise QualificationError("cross-package qualification invalid or unsupported") from exc
    # A genuine publisher/signature channel, live target credentials, real
    # durable recovery and reliable production observation have NOT been tested.
    unresolved = [
        "publisher-signature-and-authenticated-trust-custody",
        "independent-CI-policy-and-release-approval",
        "real-target-deployment-and-dispatch-adapter",
        "disk-durable-multiprocess-fencing-and-recovery",
        "live-observability-incident-ledger-and-operations",
        "SF-17-SF-18-optional-agent-budget-features-deferred",
    ]
    return {
        "schemaVersion": 1, "kind": "sf19-factory-development-qualification",
        "status": "offline-development-fixture-passed-production-blocked",
        "targetProfileId": profile["project"]["id"],
        "source": release["source"], "artifactSha256": verified_lock["bundleSha256"],
        "installedOwnedBytesRechecked": True,
        "installedMemberCount": len(members),
        "syntheticScenariosPassed": simulated["scenariosPassed"],
        "syntheticScenariosRequired": simulated["scenariosRequired"],
        "operationsDisposition": operations["status"],
        "operationsIncidents": len(operations["incidents"]),
        "operationsProposals": len(operations["workItemProposals"]),
        "developmentFixturePassed": True,
        "publisherAuthenticityVerified": False,
        "externalReleaseAuthorityVerified": False,
        "realDeploymentExercised": False,
        "durableRecoveryVerified": False,
        "liveOperationsVerified": False,
        "independentCIVerified": False,
        "productionBlockers": unresolved,
        "accepted": False, "mergeAuthorized": False,
        "releaseQualified": False, "productionReady": False,
        "deploymentAuthorized": False, "readOnly": True,
    }
