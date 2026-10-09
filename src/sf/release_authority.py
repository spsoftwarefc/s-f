"""PQ-02 reference verifier: independently pinned provider policy and HMAC grant.

This is an opt-in, single-operator observation interface. No effect authority,
revocation service, replay fence or checkout attestation is implied.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .ci_evidence import validate_request, verify_github

SHA256 = re.compile(r"[0-9a-f]{64}\Z")
IDENT = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,127}\Z")
MAX_POLICY = 1024 * 1024
GRANT_FIELDS = {
    "schemaVersion", "kind", "issuer", "grantId", "operationId",
    "destination", "environment", "effect", "artifactSha256",
    "policySha256", "expiresAt", "revocationEpoch",
}


class AuthorityError(ValueError):
    """Invalid source, identity, grant or operator trust input."""


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _unique(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise AuthorityError("duplicate JSON key")
        result[k] = v
    return result


def _read(path: Path) -> bytes:
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise AuthorityError("unsafe or missing operator input")
    if not 0 < path.stat().st_size <= MAX_POLICY:
        raise AuthorityError("oversized or empty operator input")
    return path.read_bytes()


def _digest_pin(raw: bytes, expected: str) -> None:
    if type(expected) is not str or SHA256.fullmatch(expected) is None:
        raise AuthorityError("invalid independently supplied policy digest")
    if not hmac.compare_digest(hashlib.sha256(raw).hexdigest(), expected):
        raise AuthorityError("operator policy digest mismatch")


def observe_pinned_ci(policy_file: Path, expected_policy_sha256: str, *, fetcher=None) -> dict:
    """Query provider with an exact externally hashed request; never accept it as a grant."""
    raw = _read(policy_file)
    _digest_pin(raw, expected_policy_sha256)
    try:
        policy = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise AuthorityError("invalid CI policy JSON") from exc
    if canonical(policy) != raw:
        raise AuthorityError("noncanonical CI policy")
    policy = validate_request(policy)
    result = verify_github(policy, fetcher=fetcher)
    return {**result, "independentPolicyDigestMatched": True,
            "independentPolicyCustodyVerified": False,
            "effectAuthorized": False, "accepted": False}


def _timestamp(raw: object) -> datetime:
    if type(raw) is not str or re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", raw) is None:
        raise AuthorityError("invalid grant expiration")
    try:
        return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise AuthorityError("invalid grant expiration") from exc


def observe_reference_grant(
    grant: dict, signature_sha256: str, operator_secret: bytes, *,
    effect: str, destination: str, environment: str, artifact_sha256: str,
    policy_sha256: str, minimum_revocation_epoch: int,
    now: datetime | None = None,
) -> dict:
    """Verify reference HMAC and scope; does NOT authorize a target effect.

    Operator must authenticate and safeguard the external secret separately.
    Replay, key rotation and revocation persistence are NOT implemented here.
    """
    if type(grant) is not dict or set(grant) != GRANT_FIELDS:
        raise AuthorityError("incorrect grant fields")
    if grant["schemaVersion"] != 1 or type(grant["schemaVersion"]) is not int or (
            grant["kind"] != "sf-reference-effect-grant"):
        raise AuthorityError("unsupported reference grant")
    for key in ("issuer", "grantId", "operationId", "destination",
                "environment", "effect"):
        value = grant[key]
        if type(value) is not str or IDENT.fullmatch(value) is None:
            raise AuthorityError("invalid grant identity: " + key)
    for key in ("artifactSha256", "policySha256"):
        if type(grant[key]) is not str or SHA256.fullmatch(grant[key]) is None:
            raise AuthorityError("invalid grant digest")
    if (type(minimum_revocation_epoch) is not int
            or minimum_revocation_epoch < 0
            or type(grant["revocationEpoch"]) is not int
            or grant["revocationEpoch"] < minimum_revocation_epoch):
        raise AuthorityError("revoked or invalid grant epoch")
    clock = (now or datetime.now(timezone.utc))
    if clock.tzinfo is None:
        raise AuthorityError("timezone-aware clock required")
    if _timestamp(grant["expiresAt"]) <= clock.astimezone(timezone.utc):
        raise AuthorityError("expired reference grant")
    if (grant["effect"], grant["destination"], grant["environment"],
            grant["artifactSha256"], grant["policySha256"]) != (
            effect, destination, environment, artifact_sha256, policy_sha256):
        raise AuthorityError("grant effect, destination, artifact or policy mismatch")
    if type(operator_secret) is not bytes or len(operator_secret) < 32:
        raise AuthorityError("operator secret must be supplied independently")
    if type(signature_sha256) is not str or SHA256.fullmatch(signature_sha256) is None:
        raise AuthorityError("invalid grant MAC")
    actual = hmac.new(operator_secret, canonical(grant), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(actual, signature_sha256):
        raise AuthorityError("unauthenticated reference grant")
    return {"schemaVersion": 1, "kind": "sf-pq02-reference-grant-observation",
            "grantId": grant["grantId"], "operationId": grant["operationId"],
            "artifactSha256": artifact_sha256, "scopeMatched": True,
            "hmacVerified": True, "effectAuthorized": False,
            "releaseQualified": False, "accepted": False}
