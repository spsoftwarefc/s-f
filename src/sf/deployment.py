"""SF-15: isolated fake-target deployment/recovery state machine.

No live deployment adapter, sockets, credentials, process execution or filesystem
writes. A retained in-memory ledger models durable records, but does NOT attest
fsync, cross-process fencing or real provider dispatch semantics.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import date, datetime, timezone
from typing import Any

HEX64 = re.compile(r"[0-9a-f]{64}\Z")
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
IDENT = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,127}\Z")
STATES = frozenset({"PREPARED", "DISPATCHED", "UNKNOWN", "DEPLOYED", "MIGRATION_FAILED",
                    "UNHEALTHY", "HEALTHY", "COMPENSATION_UNKNOWN", "COMPENSATED",
                    "RECOVERY_BLOCKED"})
TERMINAL = frozenset({"HEALTHY", "COMPENSATED", "MIGRATION_FAILED"})
SCENARIOS = ("healthy", "concurrent", "stale-authorization", "migration-failure",
             "crash-after-dispatch", "unknown-outcome", "health-failure",
             "compensation", "unknown-recovery", "stale-fence")
EXPECTED = {
    "healthy": "HEALTHY", "concurrent": "CONFLICT_BLOCKED",
    "stale-authorization": "AUTHORITY_BLOCKED",
    "migration-failure": "MIGRATION_FAILED", "crash-after-dispatch": "DEPLOYED",
    "unknown-outcome": "DEPLOYED", "health-failure": "UNHEALTHY",
    "compensation": "COMPENSATED", "unknown-recovery": "UNKNOWN",
    "stale-fence": "AUTHORITY_BLOCKED",
}


class DeploymentError(ValueError):
    """Unsafe simulated authorization, source, state or lifecycle transition."""


class SimulatedCrash(RuntimeError):
    """Deterministically injected loss of coordinator response after dispatch."""


class UnknownOutcome(RuntimeError):
    """Target may have committed the effect, but the reply was lost."""


def _hash(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       allow_nan=False, ensure_ascii=True) + "\n").encode("utf-8")


def _identity(value: Any, what: str) -> str:
    if type(value) is not str or not IDENT.fullmatch(value):
        raise DeploymentError(f"{what}: invalid identity")
    return value


def _sha(value: Any, what: str, *, git: bool = False) -> str:
    if type(value) is not str or not (HEX40 if git else HEX64).fullmatch(value):
        raise DeploymentError(f"{what}: invalid digest")
    return value


def _exact(value: Any, names: set[str], what: str) -> dict:
    if type(value) is not dict or set(value) != names:
        raise DeploymentError(f"{what}: missing or unknown fields")
    return value


def _expiry(value: Any, today: date) -> date:
    if type(value) is not str or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise DeploymentError("invalid grant expiration")
    try:
        expiry = date.fromisoformat(value)
    except ValueError as exc:
        raise DeploymentError("invalid grant expiration") from exc
    if expiry < today:
        raise DeploymentError("stale deployment authorization")
    return expiry


def validate_release_plan(value: Any) -> dict:
    """Consume an SF-14 plan only as a fake scenario identity, never authority."""
    p = _exact(value, {"schemaVersion", "kind", "status", "source", "sourceCheckoutVerified",
                       "artifact", "ci", "destination", "authorization", "migration",
                       "recovery", "requestSha256", "externalApprovalPinSha256",
                       "approvedReleaseOriginAuthenticated", "independentSourceAcceptanceVerified",
                       "deploymentAuthorized", "artifactDeployed", "releaseQualified", "accepted",
                       "readOnly"}, "SF-14 release plan")
    if (type(p["schemaVersion"]) is not int or p["schemaVersion"] != 1
            or p["kind"] != "sf-offline-release-plan"
            or p["status"] != "matches-external-approval-pin-not-authenticated"
            or any(p[key] is not False for key in
                   ("approvedReleaseOriginAuthenticated", "independentSourceAcceptanceVerified",
                    "deploymentAuthorized", "artifactDeployed", "releaseQualified", "accepted"))
            or p["sourceCheckoutVerified"] is not True or p["readOnly"] is not True):
        raise DeploymentError("not an unqualified SF-14 offline planning result")
    source = _exact(p["source"], {"repository", "commit", "tree"}, "source")
    if (type(source["repository"]) is not str or
            not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", source["repository"])):
        raise DeploymentError("invalid source repository")
    _sha(source["commit"], "source.commit", git=True)
    _sha(source["tree"], "source.tree", git=True)
    artifact = _exact(p["artifact"], {"kind", "sha256"}, "artifact")
    _identity(artifact["kind"], "artifact kind")
    _sha(artifact["sha256"], "artifact")
    ci = _exact(p["ci"], {"runId", "attempt", "receiptSha256",
                          "providerMetadataClaimReverifiedLive"}, "CI")
    if (type(ci["runId"]) is not int or ci["runId"] < 1
            or type(ci["attempt"]) is not int or ci["attempt"] < 1
            or ci["providerMetadataClaimReverifiedLive"] is not False):
        raise DeploymentError("unsupported CI receipt binding")
    _sha(ci["receiptSha256"], "CI receipt")
    dest = _exact(p["destination"], {"targetId", "environment", "adapter"}, "destination")
    for k in dest:
        _identity(dest[k], "destination." + k)
    auth = _exact(p["authorization"], {"principal", "grantId", "expiresOn"}, "authorization")
    _identity(auth["principal"], "principal")
    _identity(auth["grantId"], "grantId")
    _expiry(auth["expiresOn"], date(1970, 1, 1))
    for k in ("migration", "recovery"):
        procedure = _exact(p[k], {"path", "sha256", "disposition"}, k)
        if type(procedure["path"]) is not str or not procedure["path"]:
            raise DeploymentError(k + ": missing plan path")
        _sha(procedure["sha256"], k)
        if procedure["disposition"] not in ("forward", "rollback", "restore", "no-change"):
            raise DeploymentError(k + ": unrecognized disposition")
    _sha(p["requestSha256"], "release request")
    _sha(p["externalApprovalPinSha256"], "external pin")
    return copy.deepcopy(p)


def _intent(plan: dict) -> str:
    return _hash(_json({"request": plan["requestSha256"],
                        "artifact": plan["artifact"]["sha256"],
                        "target": plan["destination"],
                        "grant": plan["authorization"]["grantId"]}))


class FakeTarget:
    """Separate in-memory state with monotonic fences and idempotent dispatch."""
    def __init__(self, destination: dict):
        self.destination = copy.deepcopy(destination)
        self.fence = 0
        self.applied: dict[str, dict] = {}
        self.active_artifact: str | None = None
        self.migration_keys: set[str] = set()
        self.dispatch_count = 0
        self.health_good = True
        self.reconcile_available = True
        self.compensation_unknown = False

    def reserve_fence(self, generation: int) -> None:
        if type(generation) is not int or generation <= self.fence:
            raise DeploymentError("stale target fencing token")
        self.fence = generation

    def dispatch(self, *, key: str, epoch: int, plan: dict, ambiguous: bool = False) -> dict:
        if epoch != self.fence:
            raise DeploymentError("stale target fencing token")
        if plan["destination"] != self.destination:
            raise DeploymentError("target identity mismatch")
        observed = self.applied.get(key)
        if observed is None:
            observed = {"key": key, "artifactSha256": plan["artifact"]["sha256"],
                        "sourceCommit": plan["source"]["commit"],
                        "grantId": plan["authorization"]["grantId"], "epoch": epoch,
                        "destination": copy.deepcopy(self.destination)}
            self.applied[key] = observed
            self.active_artifact = observed["artifactSha256"]
            self.dispatch_count += 1
        elif observed != {"key": key, "artifactSha256": plan["artifact"]["sha256"],
                          "sourceCommit": plan["source"]["commit"],
                          "grantId": plan["authorization"]["grantId"], "epoch": epoch,
                          "destination": copy.deepcopy(self.destination)}:
            raise DeploymentError("idempotency collision with different effect identity")
        if ambiguous:
            raise UnknownOutcome("target applied but response was lost")
        return copy.deepcopy(observed)

    def reconcile(self, key: str) -> dict | None:
        if not self.reconcile_available:
            raise UnknownOutcome("authoritative target outcome unavailable")
        return copy.deepcopy(self.applied.get(key))

    def compensate(self, key: str, epoch: int, previous: str | None) -> None:
        if epoch != self.fence or key not in self.applied:
            raise DeploymentError("unsafe recovery identity or fence")
        if self.compensation_unknown:
            raise UnknownOutcome("compensation disposition unknown")
        self.active_artifact = previous


class MemoryLedger:
    """Persistent-across-controller fixture *model*, not actual durable storage."""
    def __init__(self):
        self.owner: str | None = None
        self.epoch = 0
        self.record: dict | None = None

    def acquire(self, owner: str, epoch: int) -> None:
        _identity(owner, "operator")
        if self.owner is not None and self.owner != owner:
            raise DeploymentError("concurrent deployment owner holds the lease")
        if type(epoch) is not int or epoch <= self.epoch:
            raise DeploymentError("stale deployment fence")
        self.owner = owner
        self.epoch = epoch

    def release(self, owner: str) -> None:
        if self.owner != owner:
            raise DeploymentError("cannot release foreign deployment owner")
        self.owner = None

    def transition(self, new_state: str, *, event: str) -> None:
        if self.record is None or new_state not in STATES:
            raise DeploymentError("no valid persisted deployment record")
        self.record["state"] = new_state
        self.record["events"].append(event)


class FakeCoordinator:
    def __init__(self, ledger: MemoryLedger, target: FakeTarget, *, today: date):
        self.ledger = ledger
        self.target = target
        self.today = today

    def _authority(self, plan: dict, owner: str, epoch: int, revoked: bool = False) -> None:
        _identity(owner, "owner")
        if revoked:
            raise DeploymentError("deployment authorization revoked")
        if owner != plan["authorization"]["principal"]:
            raise DeploymentError("principal does not match approved release plan")
        _expiry(plan["authorization"]["expiresOn"], self.today)
        if plan["destination"] != self.target.destination:
            raise DeploymentError("wrong target identity")
        if type(epoch) is not int or epoch < 1:
            raise DeploymentError("invalid fencing epoch")

    def start(self, value: dict, *, owner: str, epoch: int, fault: str = "none",
              revoked: bool = False) -> dict:
        """Persist intent, simulate migration, persist dispatch, then fake target."""
        plan = validate_release_plan(value)
        self._authority(plan, owner, epoch, revoked)
        if self.ledger.record is not None:
            raise DeploymentError("unsettled operation; reconcile before another deployment")
        # Neither an in-memory lock nor SF-14's candidate plan is a live grant.
        self.ledger.acquire(owner, epoch)
        self.target.reserve_fence(epoch)
        key = _intent(plan)
        self.ledger.record = {"schemaVersion": 1, "intentKey": key,
                              "releasePlanDigest": _hash(_json(plan)),
                              "plan": plan, "owner": owner, "epoch": epoch,
                              "previousArtifact": self.target.active_artifact,
                              "state": "PREPARED", "events": ["intent-persisted"]}
        if fault == "migration":
            self.ledger.transition("MIGRATION_FAILED", event="migration-rejected")
            return copy.deepcopy(self.ledger.record)
        # The synthetic migration has no real effect or backend executor.
        self.target.migration_keys.add(key)
        self.ledger.record["events"].append("migration-simulated")
        self.ledger.transition("DISPATCHED", event="dispatch-intent-persisted")
        try:
            self.target.dispatch(key=key, epoch=epoch, plan=plan, ambiguous=fault == "unknown")
        except UnknownOutcome:
            self.ledger.transition("UNKNOWN", event="dispatch-outcome-unknown")
            return copy.deepcopy(self.ledger.record)
        if fault == "crash":
            raise SimulatedCrash("coordinator crashed after fake target dispatch")
        self.ledger.transition("DEPLOYED", event="dispatch-receipt-confirmed")
        if fault == "health":
            self.target.health_good = False
        if not self.target.health_good:
            self.ledger.transition("UNHEALTHY", event="health-rejected")
            return copy.deepcopy(self.ledger.record)
        self.ledger.transition("HEALTHY", event="health-confirmed")
        return copy.deepcopy(self.ledger.record)

    def recover(self, *, owner: str, epoch: int, revoked: bool = False) -> dict:
        record = self.ledger.record
        if record is None:
            raise DeploymentError("no recorded deployment to reconcile")
        plan = validate_release_plan(record["plan"])
        self._authority(plan, owner, epoch, revoked)
        if record["owner"] != owner or record["epoch"] != epoch or self.ledger.epoch != epoch:
            raise DeploymentError("recovery owner or epoch mismatch")
        if record["intentKey"] != _intent(plan) or record["releasePlanDigest"] != _hash(_json(plan)):
            raise DeploymentError("corrupt persisted release identity")
        if self.target.fence != epoch:
            raise DeploymentError("recovery target fence superseded")
        if record["state"] not in ("UNKNOWN", "DISPATCHED", "COMPENSATION_UNKNOWN"):
            return copy.deepcopy(record)
        if record["state"] == "COMPENSATION_UNKNOWN":
            # No automatic repetition of compensation without a typed status receipt.
            return copy.deepcopy(record)
        try:
            receipt = self.target.reconcile(record["intentKey"])
        except UnknownOutcome:
            if record["state"] != "UNKNOWN":
                self.ledger.transition("UNKNOWN", event="target-query-unavailable")
            else:
                record["events"].append("target-query-unavailable")
            return copy.deepcopy(record)
        if receipt is None:
            self.ledger.transition("UNKNOWN", event="authoritative-receipt-absent-no-retry")
            return copy.deepcopy(record)
        expected = {"key": record["intentKey"], "artifactSha256": plan["artifact"]["sha256"],
                    "sourceCommit": plan["source"]["commit"],
                    "grantId": plan["authorization"]["grantId"], "epoch": epoch,
                    "destination": copy.deepcopy(self.target.destination)}
        if receipt != expected:
            self.ledger.transition("RECOVERY_BLOCKED", event="target-receipt-mismatch")
            return copy.deepcopy(record)
        self.ledger.transition("DEPLOYED", event="target-receipt-reconciled")
        if self.target.health_good:
            self.ledger.transition("HEALTHY", event="health-confirmed")
        else:
            self.ledger.transition("UNHEALTHY", event="health-rejected")
        return copy.deepcopy(record)

    def compensate(self, *, owner: str, epoch: int) -> dict:
        record = self.ledger.record
        if record is None or record["state"] != "UNHEALTHY":
            raise DeploymentError("no confirmed unhealthy effect to compensate")
        plan = validate_release_plan(record["plan"])
        self._authority(plan, owner, epoch)
        if (record["owner"] != owner or record["epoch"] != epoch
                or self.ledger.epoch != epoch or self.target.fence != epoch):
            raise DeploymentError("compensation authority or fence mismatch")
        record["events"].append("recovery-intent-persisted")
        try:
            self.target.compensate(record["intentKey"], epoch, record["previousArtifact"])
        except UnknownOutcome:
            self.ledger.transition("COMPENSATION_UNKNOWN", event="compensation-outcome-unknown")
            return copy.deepcopy(record)
        self.ledger.transition("COMPENSATED", event="compensation-confirmed")
        return copy.deepcopy(record)


def run_scenario(plan_value: dict, scenario: str, *, today: date | None = None) -> dict:
    """Independent deterministic one-scenario fake-target proof."""
    plan = validate_release_plan(plan_value)
    if scenario not in EXPECTED:
        raise DeploymentError("unsupported qualification scenario")
    today = today or datetime.now(timezone.utc).date()
    ledger = MemoryLedger()
    target = FakeTarget(plan["destination"])
    agent = FakeCoordinator(ledger, target, today=today)
    owner = plan["authorization"]["principal"]
    status = None
    if scenario == "stale-authorization":
        try:
            agent.start(plan, owner=owner, epoch=1, revoked=True)
        except DeploymentError:
            status = "AUTHORITY_BLOCKED"
    elif scenario == "stale-fence":
        target.reserve_fence(2)
        try:
            agent.start(plan, owner=owner, epoch=1)
        except DeploymentError:
            status = "AUTHORITY_BLOCKED"
    elif scenario == "concurrent":
        ledger.acquire("another-operator", 1)
        try:
            agent.start(plan, owner=owner, epoch=2)
        except DeploymentError:
            status = "CONFLICT_BLOCKED"
    else:
        fault = {"migration-failure": "migration", "crash-after-dispatch": "crash",
                 "unknown-outcome": "unknown", "unknown-recovery": "unknown",
                 "health-failure": "health", "compensation": "health"}.get(scenario, "none")
        try:
            agent.start(plan, owner=owner, epoch=1, fault=fault)
        except SimulatedCrash:
            pass
        if scenario in ("crash-after-dispatch", "unknown-outcome", "unknown-recovery"):
            if scenario == "unknown-recovery":
                target.reconcile_available = False
            agent = FakeCoordinator(ledger, target, today=today)  # logical restart
            agent.recover(owner=owner, epoch=1)
        if scenario == "compensation":
            agent.compensate(owner=owner, epoch=1)
        status = ledger.record["state"]
    events = [] if ledger.record is None else list(ledger.record["events"])
    expected = EXPECTED[scenario]
    # Event checks are NOT based solely on the final state.
    safe = {
        "healthy": "health-confirmed" in events,
        "concurrent": ledger.record is None,
        "stale-authorization": ledger.record is None,
        "migration-failure": "dispatch-intent-persisted" not in events,
        "crash-after-dispatch": "target-receipt-reconciled" in events,
        "unknown-outcome": "target-receipt-reconciled" in events,
        "health-failure": "health-rejected" in events,
        "compensation": "compensation-confirmed" in events,
        "unknown-recovery": "target-query-unavailable" in events,
        "stale-fence": ledger.record is None and target.dispatch_count == 0,
    }[scenario]
    if scenario in ("concurrent", "stale-authorization", "stale-fence", "migration-failure"):
        safe = safe and target.dispatch_count == 0
    if scenario in ("crash-after-dispatch", "unknown-outcome", "unknown-recovery"):
        safe = safe and target.dispatch_count == 1
    return {"scenario": scenario, "expected": expected, "observed": status,
            "events": events, "dispatchCount": target.dispatch_count,
            "passed": status == expected and safe}


def qualify_deployment(plan: dict, *, today: date | None = None) -> dict:
    """Run a fixed independent fake-target matrix; all scenarios must pass."""
    value = validate_release_plan(plan)
    cases = [run_scenario(value, scenario, today=today) for scenario in SCENARIOS]
    all_pass = len(cases) == len(SCENARIOS) and all(x["passed"] for x in cases)
    return {"schemaVersion": 1, "kind": "sf15-fake-target-qualification",
            "status": "synthetic-passed" if all_pass else "synthetic-failed",
            "source": value["source"], "artifact": value["artifact"],
            "destination": value["destination"],
            "planSha256": _hash(_json(value)), "cases": cases,
            "scenariosPassed": sum(x["passed"] for x in cases),
            "scenariosRequired": len(SCENARIOS),
            "syntheticPassed": all_pass, "realTargetExercised": False,
            "externalAuthorityAuthenticated": False, "diskDurabilityVerified": False,
            "distributedFenceQualified": False, "accepted": False,
            "deploymentAuthorized": False, "releaseQualified": False}
