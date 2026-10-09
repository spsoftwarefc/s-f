"""PQ-07A: read-only source-bound qualification dossier gap assessment.

This validates candidate-authored *claims*, not their issuers. A complete
dossier cannot authenticate itself or qualify a release/deployment.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

MAX_BYTES = 512 * 1024
MAX_ROWS = 32
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
IDENT = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,127}\Z")
REQUIRED_CLAIMS = (
    "publisher-authenticity", "independent-ci", "effect-grant",
    "retained-build", "installer-lifecycle", "durable-recovery",
    "reference-deployment", "live-operations",
)
ROOT_FIELDS = {"schemaVersion", "kind", "candidate", "profile", "evidence", "excludedCapabilities"}
CANDIDATE_FIELDS = {"sourceCommit", "sourceTree", "artifactSha256", "releaseId"}
PROFILE_FIELDS = {"scopeId", "platform", "adapter", "environment"}
ROW_FIELDS = {"claim", "sourceCommit", "sourceTree", "artifactSha256",
              "evidenceSha256", "issuer", "negativeCaseSha256", "disposition"}
ALLOWED_DISPOSITIONS = {"observed", "failed", "unavailable"}
ALLOWED_EXCLUSIONS = {"SF-17-agent-host", "SF-18-shared-budget"}


class DossierError(ValueError):
    """Malformed, unsupported, contradictory or unbounded dossier structure."""


def _unique(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise DossierError("duplicate dossier JSON member")
        out[key] = value
    return out


def _id(value, label):
    if type(value) is not str or not IDENT.fullmatch(value):
        raise DossierError("invalid " + label)


def _sha(value, label, *, git=False):
    match = HEX40 if git else HEX64
    if type(value) is not str or not match.fullmatch(value):
        raise DossierError("invalid " + label)


def _exact(value, keys, label):
    if type(value) is not dict or set(value) != keys:
        raise DossierError("unsupported " + label + " fields")
    return value


def read_dossier(path: Path) -> dict:
    """Bounded, strict, no-last-component-symlink JSON input."""
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise DossierError("dossier path must be a regular absolute file")
    size = path.stat().st_size
    if not 0 < size <= MAX_BYTES:
        raise DossierError("empty or oversized dossier")
    raw = path.read_bytes()
    if len(raw) != size:
        raise DossierError("changed or oversized dossier")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise DossierError("invalid dossier JSON") from exc
    return _exact(value, ROOT_FIELDS, "dossier")


def assess_dossier(dossier: dict) -> dict:
    """Classify submitted rows without interpreting them as trusted attestations.

    The source-independent verifier/credential/store bindings are deliberately
    absent from this adapter; production acceptance remains false always.
    """
    document = _exact(dossier, ROOT_FIELDS, "dossier")
    if type(document["schemaVersion"]) is not int or document["schemaVersion"] != 1:
        raise DossierError("unsupported dossier schema")
    if document["kind"] != "sf-pq07a-source-dossier":
        raise DossierError("unsupported dossier kind")
    candidate = _exact(document["candidate"], CANDIDATE_FIELDS, "candidate")
    for key in ("sourceCommit", "sourceTree"):
        _sha(candidate[key], key, git=True)
    _sha(candidate["artifactSha256"], "artifactSha256")
    _id(candidate["releaseId"], "release ID")
    profile = _exact(document["profile"], PROFILE_FIELDS, "profile")
    for name in PROFILE_FIELDS:
        _id(profile[name], name)
    exclusions = document["excludedCapabilities"]
    if (type(exclusions) is not list or len(exclusions) != len(set(
            e for e in exclusions if type(e) is str))
            or any(type(e) is not str or e not in ALLOWED_EXCLUSIONS
                   for e in exclusions)):
        raise DossierError("invalid or duplicate excluded capabilities")
    evidence = document["evidence"]
    if type(evidence) is not list or len(evidence) > MAX_ROWS:
        raise DossierError("unbounded evidence rows")
    claims = {}
    for row in evidence:
        _exact(row, ROW_FIELDS, "evidence")
        if type(row["claim"]) is not str or row["claim"] not in REQUIRED_CLAIMS:
            raise DossierError("unknown claim")
        if row["claim"] in claims:
            raise DossierError("duplicate claim evidence row")
        for name in ("sourceCommit", "sourceTree"):
            _sha(row[name], "evidence " + name, git=True)
        for name in ("artifactSha256", "evidenceSha256", "negativeCaseSha256"):
            _sha(row[name], "evidence " + name)
        _id(row["issuer"], "evidence issuer label")
        if (type(row["disposition"]) is not str
                or row["disposition"] not in ALLOWED_DISPOSITIONS):
            raise DossierError("unsupported claim disposition")
        claims[row["claim"]] = row
    supported = (
        profile["platform"] == "linux"
        and profile["adapter"] == "disposable-single-host"
        and profile["environment"] == "test"
    )
    observed = []
    for claim in REQUIRED_CLAIMS:
        row = claims.get(claim)
        if not supported:
            state = "unsupported-profile"
        elif row is None:
            state = "missing"
        elif (row["sourceCommit"], row["sourceTree"], row["artifactSha256"]) != (
                candidate["sourceCommit"], candidate["sourceTree"],
                candidate["artifactSha256"]):
            state = "identity-rejected"
        elif row["disposition"] == "observed":
            state = "present-unverified"
        else:
            state = row["disposition"]
        observed.append({"claim": claim, "state": state})
    return {
        "schemaVersion": 1, "kind": "sf-pq07a-dossier-gap-report",
        "candidate": candidate, "profile": profile,
        "inputSha256": hashlib.sha256(
            (json.dumps(document, sort_keys=True, separators=(",", ":"),
                        ensure_ascii=True, allow_nan=False) + "\n").encode("utf-8")
        ).hexdigest(),
        "claimStates": observed,
        "scopeSupportedForReference": supported,
        "externalIssuerAuthenticityVerified": False,
        "providerAndTargetEvidenceIndependentlyVerified": False,
        "SF_R10": "UNMET-overall",
        "accepted": False, "productionQualified": False,
        "status": "not-qualified",
        "limitations": [
            "Candidate-supplied evidence digest and issuer labels have no authority",
            "Publisher/CI/release-grant/retention/live target and incident independent proofs missing",
            "Adopter, production VPS, multi-host and Windows deployment scope not qualified",
        ],
    }
