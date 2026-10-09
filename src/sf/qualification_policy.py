"""PQ-07B: strict operator-hashed policy intake, not independently authorized custody."""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path

from .production_dossier import REQUIRED_CLAIMS, assess_dossier, DossierError

HASH = re.compile(r"[0-9a-f]{64}\Z")
GIT = re.compile(r"[0-9a-f]{40}\Z")
ID = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,127}\Z")
POLICY_KEYS = {"schemaVersion", "kind", "sourceCommit", "sourceTree",
               "artifactSha256", "profile", "requiredClaims", "policyEpoch",
               "expiresOn", "minimumEvidenceCount"}
PROFILE_KEYS = {"scopeId", "platform", "adapter", "environment"}
MAX_BYTES = 128 * 1024


class PolicyError(ValueError):
    """Unavailable, mismatched or unqualified acceptance policy."""


def _pairs(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise PolicyError("duplicate policy field")
        out[k] = v
    return out


def _canonical(obj):
    return (json.dumps(obj, sort_keys=True, ensure_ascii=True,
                       allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")


def _policy(path: Path, expected_sha256: str, *, today: date | None) -> dict:
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise PolicyError("invalid operator policy path")
    if type(expected_sha256) is not str or not HASH.fullmatch(expected_sha256):
        raise PolicyError("invalid out-of-band policy digest")
    if not 0 < path.stat().st_size <= MAX_BYTES:
        raise PolicyError("operator policy size invalid")
    raw = path.read_bytes()
    if len(raw) > MAX_BYTES or not hmac.compare_digest(
            hashlib.sha256(raw).hexdigest(), expected_sha256):
        raise PolicyError("pinned policy digest mismatch")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise PolicyError("invalid pinned policy JSON") from exc
    if type(value) is not dict or set(value) != POLICY_KEYS or raw != _canonical(value):
        raise PolicyError("unknown or noncanonical policy")
    if type(value["schemaVersion"]) is not int or value["schemaVersion"] != 1 or (
            value["kind"] != "sf-pq07-qualification-policy"):
        raise PolicyError("unsupported policy")
    for key in ("sourceCommit", "sourceTree"):
        if type(value[key]) is not str or not GIT.fullmatch(value[key]):
            raise PolicyError("invalid policy source identity")
    if type(value["artifactSha256"]) is not str or not HASH.fullmatch(value["artifactSha256"]):
        raise PolicyError("invalid policy artifact")
    profile = value["profile"]
    if type(profile) is not dict or set(profile) != PROFILE_KEYS:
        raise PolicyError("invalid policy scope")
    for field in PROFILE_KEYS:
        if type(profile[field]) is not str or not ID.fullmatch(profile[field]):
            raise PolicyError("invalid policy profile: " + field)
    claims = value["requiredClaims"]
    if type(claims) is not list or claims != list(REQUIRED_CLAIMS):
        raise PolicyError("qualification claim oracle changed")
    if type(value["policyEpoch"]) is not int or not 1 <= value["policyEpoch"] <= 2**53:
        raise PolicyError("invalid policy epoch")
    if (type(value["minimumEvidenceCount"]) is not int
            or value["minimumEvidenceCount"] != len(REQUIRED_CLAIMS)):
        raise PolicyError("wrong mandatory evidence count")
    if type(value["expiresOn"]) is not str:
        raise PolicyError("invalid expiry")
    try:
        expires = date.fromisoformat(value["expiresOn"])
        if expires.isoformat() != value["expiresOn"]:
            raise ValueError("noncanonical date")
    except ValueError as exc:
        raise PolicyError("invalid expiry date") from exc
    if expires < (today or datetime.now(timezone.utc).date()):
        raise PolicyError("operator acceptance policy expired")
    return value


def assess_pinned_scope(
    policy_path: Path, expected_policy_sha256: str, dossier: dict, *,
    minimum_policy_epoch: int, today: date | None = None,
) -> dict:
    if type(minimum_policy_epoch) is not int or not 1 <= minimum_policy_epoch <= 2**53:
        raise PolicyError("operator minimum epoch invalid")
    policy = _policy(policy_path, expected_policy_sha256, today=today)
    if policy["policyEpoch"] < minimum_policy_epoch:
        raise PolicyError("operator policy rollback")
    try:
        result = assess_dossier(dossier)
    except DossierError as exc:
        raise PolicyError("invalid bound dossier") from exc
    candidate = result["candidate"]
    if (
        policy["sourceCommit"] != candidate["sourceCommit"]
        or policy["sourceTree"] != candidate["sourceTree"]
        or policy["artifactSha256"] != candidate["artifactSha256"]
        or policy["profile"] != result["profile"]
    ):
        raise PolicyError("dossier source or scope contradicts operator policy")
    return {
        "schemaVersion": 1, "kind": "sf-pq07b-policy-scope-observation",
        "policySha256": expected_policy_sha256,
        "policyEpoch": policy["policyEpoch"],
        "sourceScopeMatched": True,
        "allClaimsStructurallyPresent": all(
            item["state"] == "present-unverified" for item in result["claimStates"]
        ),
        "independentPolicyCustodyVerified": False,
        "externalClaimsVerified": False,
        "releaseAuthorized": False, "productionQualified": False, "accepted": False,
    }
