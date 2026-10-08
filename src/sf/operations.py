"""SF-16: bounded, offline operations evidence to incident/work-item *proposals*.

All inputs are caller-provided and unauthenticated. Nothing observes a live target,
resolves incidents, dispatches work or assigns real operational authority.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .deployment import SCENARIOS, EXPECTED

MAX_INPUT_BYTES = 256 * 1024
MAX_EVENTS = 128
DOMAINS = ("deployment", "health", "migration", "recovery")
STATES = ("healthy", "degraded", "failed", "unknown")
IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,95}\Z")
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SHA64 = re.compile(r"[0-9a-f]{64}\Z")
UTC_TIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")


class OperationsError(ValueError):
    """Unsafe or incoherent source-bound operations observation input."""


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True, allow_nan=False) + "\n").encode("utf-8")


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _object(value: Any, fields: set[str], name: str) -> dict:
    if type(value) is not dict or set(value) != fields:
        raise OperationsError(name + ": missing or unknown fields")
    return value


def _id(value: Any, name: str) -> str:
    if type(value) is not str or IDENTIFIER.fullmatch(value) is None:
        raise OperationsError(name + ": invalid identifier")
    return value


def _hash(value: Any, name: str, *, git: bool = False) -> str:
    if type(value) is not str or (
            SHA40 if git else SHA64).fullmatch(value) is None:
        raise OperationsError(name + ": invalid digest")
    return value


def _time(value: Any) -> datetime:
    if type(value) is not str or UTC_TIME.fullmatch(value) is None:
        raise OperationsError("timestamp must be exact UTC seconds with Z suffix")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise OperationsError("invalid observation UTC timestamp") from exc
    return parsed.replace(tzinfo=timezone.utc)


def _pairs(items: list[tuple[str, Any]]) -> dict:
    result: dict = {}
    for name, value in items:
        if name in result:
            raise OperationsError("duplicate operations JSON member")
        result[name] = value
    return result


def read_document(path: Path) -> dict:
    """Bounded, strict, non-symlinked local JSON, no source interpretation."""
    if path.is_symlink() or not path.is_file():
        raise OperationsError("missing or unsafe operations input")
    size = path.stat().st_size
    if not 0 < size <= MAX_INPUT_BYTES:
        raise OperationsError("empty or oversized operations input")
    raw = path.read_bytes()
    if len(raw) > MAX_INPUT_BYTES:
        raise OperationsError("oversized operations input")
    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs)
    except OperationsError:
        raise
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise OperationsError("invalid operations JSON") from exc
    if type(data) is not dict:
        raise OperationsError("operations input must be JSON object")
    return data


def _destination(value: Any) -> dict:
    destination = _object(value, {"targetId", "environment", "adapter"},
                          "destination")
    for name in ("targetId", "environment", "adapter"):
        _id(destination[name], "destination." + name)
    return destination


def _qualification(value: Any) -> dict:
    result = _object(value, {
        "schemaVersion", "kind", "status", "source", "artifact",
        "destination", "planSha256", "cases", "scenariosPassed",
        "scenariosRequired", "syntheticPassed", "realTargetExercised",
        "externalAuthorityAuthenticated", "diskDurabilityVerified",
        "distributedFenceQualified", "accepted", "deploymentAuthorized",
        "releaseQualified",
    }, "SF-15 qualification")
    if (type(result["schemaVersion"]) is not int or result["schemaVersion"] != 1
            or result["kind"] != "sf15-fake-target-qualification"
            or result["status"] != "synthetic-passed"
            or result["syntheticPassed"] is not True
            or any(result[field] is not False for field in (
                "realTargetExercised", "externalAuthorityAuthenticated",
                "diskDurabilityVerified", "distributedFenceQualified",
                "accepted", "deploymentAuthorized", "releaseQualified"))):
        raise OperationsError("SF-15 input is not an unqualified synthetic success")
    source = _object(result["source"], {"repository", "commit", "tree"}, "source")
    repo = source["repository"]
    if (type(repo) is not str or not re.fullmatch(
            r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo)):
        raise OperationsError("invalid source repository")
    _hash(source["commit"], "source.commit", git=True)
    _hash(source["tree"], "source.tree", git=True)
    artifact = _object(result["artifact"], {"kind", "sha256"}, "artifact")
    _id(artifact["kind"], "artifact.kind")
    _hash(artifact["sha256"], "artifact.sha256")
    _destination(result["destination"])
    _hash(result["planSha256"], "planSha256")
    if (type(result["scenariosPassed"]) is not int
            or type(result["scenariosRequired"]) is not int
            or result["scenariosPassed"] != len(SCENARIOS)
            or result["scenariosRequired"] != len(SCENARIOS)):
        raise OperationsError("incomplete fake-target qualification")
    cases = result["cases"]
    if type(cases) is not list or len(cases) != len(SCENARIOS):
        raise OperationsError("missing or duplicated SF-15 scenarios")
    for name, case in zip(SCENARIOS, cases):
        c = _object(case, {"scenario", "expected", "observed", "events",
                           "dispatchCount", "passed"}, "SF-15 scenario")
        if (c["scenario"] != name or c["expected"] != EXPECTED[name]
                or c["observed"] != EXPECTED[name] or c["passed"] is not True
                or type(c["events"]) is not list
                or not all(type(event) is str for event in c["events"])
                or type(c["dispatchCount"]) is not int
                or not 0 <= c["dispatchCount"] <= 1):
            raise OperationsError("invalid or substituted synthetic scenario")
    return result


def _policy(value: Any, expected: dict) -> dict:
    p = _object(value, {"schemaVersion", "kind", "sourceCommit",
                        "planSha256", "destination", "maxEventAgeSeconds",
                        "maxEvents", "recoveryHealthyCount", "routes"},
                "operations policy")
    if (type(p["schemaVersion"]) is not int or p["schemaVersion"] != 1
            or p["kind"] != "sf16-operations-policy"):
        raise OperationsError("unsupported operations policy")
    _hash(p["sourceCommit"], "policy source", git=True)
    _hash(p["planSha256"], "policy plan")
    if (p["sourceCommit"] != expected["source"]["commit"]
            or p["planSha256"] != expected["planSha256"]
            or _destination(p["destination"]) != expected["destination"]):
        raise OperationsError("policy source or destination binding mismatch")
    if (type(p["maxEventAgeSeconds"]) is not int
            or not 30 <= p["maxEventAgeSeconds"] <= 86400
            or type(p["maxEvents"]) is not int or not 1 <= p["maxEvents"] <= MAX_EVENTS
            or type(p["recoveryHealthyCount"]) is not int
            or not 2 <= p["recoveryHealthyCount"] <= 5):
        raise OperationsError("unsupported operations thresholds")
    routes = _object(p["routes"], set(DOMAINS), "operations routes")
    for domain in DOMAINS:
        route = _object(routes[domain], {"ownerId", "runbookId"}, domain + " route")
        _id(route["ownerId"], "incident owner")
        _id(route["runbookId"], "runbook")
    return p


def _observations(value: Any, qualification: dict, policy: dict,
                  now: datetime) -> dict:
    doc = _object(value, {"schemaVersion", "kind", "sourceCommit",
                          "planSha256", "destination", "events"}, "observations")
    if (type(doc["schemaVersion"]) is not int or doc["schemaVersion"] != 1
            or doc["kind"] != "sf16-offline-observations"):
        raise OperationsError("unsupported observations document")
    _hash(doc["sourceCommit"], "observations source", git=True)
    _hash(doc["planSha256"], "observations plan")
    if (doc["sourceCommit"] != qualification["source"]["commit"]
            or doc["planSha256"] != qualification["planSha256"]
            or _destination(doc["destination"]) != qualification["destination"]):
        raise OperationsError("observation source or target substitution")
    events = doc["events"]
    if type(events) is not list or len(events) > policy["maxEvents"]:
        raise OperationsError("observations exceed declared bounded event budget")
    seen: set[str] = set()
    previous: datetime | None = None
    for event in events:
        row = _object(event, {"eventId", "observedAt", "domain",
                              "state", "evidenceSha256"}, "observation event")
        key = _id(row["eventId"], "eventId")
        if key in seen:
            raise OperationsError("duplicate observation eventId")
        seen.add(key)
        current = _time(row["observedAt"])
        if current > now:
            raise OperationsError("future observation time")
        if previous is not None and current < previous:
            raise OperationsError("out-of-order observation time")
        previous = current
        if row["domain"] not in DOMAINS or row["state"] not in STATES:
            raise OperationsError("unsupported observation domain or state")
        _hash(row["evidenceSha256"], "event evidence")
    return doc


def assess_operations(qualification: dict, policy: dict, observations: dict,
                      *, now: datetime | None = None) -> dict:
    """Pure bounded snapshot report: never promote synthetic input to live health."""
    current = now if now is not None else datetime.now(timezone.utc)
    if (not isinstance(current, datetime) or current.tzinfo is None
            or current.utcoffset() != timedelta(0)):
        raise OperationsError("assessment clock must be UTC aware")
    current = current.astimezone(timezone.utc)
    q = _qualification(qualification)
    p = _policy(policy, q)
    doc = _observations(observations, q, p, current)
    health = []
    incidents = []
    work = []
    for domain in DOMAINS:
        events = [event for event in doc["events"] if event["domain"] == domain]
        last = events[-1] if events else None
        latest_ok = last is not None and (
            current - _time(last["observedAt"])).total_seconds() <= p["maxEventAgeSeconds"]
        anomalies = [e for e in events if e["state"] != "healthy"]
        trailing_healthy = 0
        for event in reversed(events):
            if event["state"] != "healthy":
                break
            trailing_healthy += 1
        eligible = bool(anomalies and latest_ok and
                        trailing_healthy >= p["recoveryHealthyCount"])
        if not events:
            status, reason = "unknown", "no-observations"
        elif not latest_ok:
            status, reason = "unknown", "stale-observations"
        elif anomalies and eligible:
            status, reason = "recovery-review", "explicit-incident-closure-required"
        elif anomalies and last["state"] == "healthy":
            status, reason = "unresolved", "insufficient-healthy-evidence"
        elif anomalies:
            status, reason = last["state"], "unresolved-signal"
        else:
            status, reason = "healthy-observed", "unverified-offline-snapshot"
        health.append({"domain": domain, "status": status, "reason": reason,
                       "latestEventId": last["eventId"] if last else None,
                       "fresh": latest_ok, "incidentClosureAuthorized": False})
        if not anomalies:
            continue
        first = anomalies[0]
        suffix = _digest(_canonical({"plan": q["planSha256"], "domain": domain,
                                     "first": first["eventId"]}))[:24]
        incident_id = "sf16-incident-" + suffix
        severity = ("critical" if any(e["state"] == "failed" for e in anomalies) else
                    "high" if any(e["state"] == "unknown" for e in anomalies) else "medium")
        route = p["routes"][domain]
        incident = {"incidentId": incident_id, "domain": domain, "severity": severity,
                    "status": "recovery-review-required" if eligible else "open-review-required",
                    "ownerId": route["ownerId"], "runbookId": route["runbookId"],
                    "firstEventId": first["eventId"],
                    "lastEventId": last["eventId"],
                    "recoveryEvidenceEligible": eligible, "acknowledged": False,
                    "resolved": False}
        incidents.append(incident)
        work.append({"proposalId": "sf16-work-" + suffix, "kind": "incident-investigation",
                     "incidentId": incident_id, "domain": domain,
                     "sourceCommit": q["source"]["commit"], "planSha256": q["planSha256"],
                     "ownerId": route["ownerId"], "runbookId": route["runbookId"],
                     "evidenceSha256": first["evidenceSha256"],
                     "requiresOperatorApproval": True, "created": False})
    if incidents:
        status = "incident-review-required"
    elif any(item["status"] == "unknown" for item in health):
        status = "observation-incomplete"
    else:
        status = "healthy-observed-unverified"
    return {
        "schemaVersion": 1, "kind": "sf16-operations-assessment",
        "status": status,
        "sourceCommit": q["source"]["commit"], "planSha256": q["planSha256"],
        "destination": q["destination"],
        "qualificationDigest": _digest(_canonical(q)),
        "policyDigest": _digest(_canonical(p)),
        "observationDigest": _digest(_canonical(doc)),
        "eventsObserved": len(doc["events"]),
        "health": health, "incidents": incidents, "workItemProposals": work,
        "source": "offline-caller-supplied-unauthenticated",
        "liveHealthVerified": False, "incidentResolved": False,
        "workItemsCreated": False, "notificationsSent": False,
        "releaseQualified": False, "deploymentAuthorized": False,
        "accepted": False, "readOnly": True,
    }
