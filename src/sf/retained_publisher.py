"""PQ-07P: exact retained bytes bridge to opt-in publisher authenticity observation.

This is read-only verification, NOT permission to install or publish.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import tempfile
from datetime import date
from pathlib import Path

from .publisher import PublisherError, authenticate_publisher
from .retained_artifact import RetentionError, _canonical, read_retained

HASH = re.compile(r"[0-9a-f]{64}\Z")


class RetainedPublisherError(ValueError):
    """Retained artifact, operator pin, or publisher observations disagree."""


def review_retained_publisher(
    store: Path, artifact_sha256: str, manifest_sha256: str,
    *, release_pin: Path, policy: Path, policy_sha256: str,
    attestation: Path, verifier: Path, trusted_root: Path,
    minimum_release_epoch: int, today: date | None = None,
) -> dict:
    """Verify a private byte copy; never expose an installer or effect handle.

    Manifest/policy SHA-256 values MUST be independently supplied, not
    parsed from candidate manifests. This does not authenticate their custody.
    """
    if any(type(item) is not str or HASH.fullmatch(item) is None for item in
           (artifact_sha256, manifest_sha256, policy_sha256)):
        raise RetainedPublisherError("invalid independently pinned digest")
    try:
        manifest, archive = read_retained(store, artifact_sha256, today=today)
    except (RetentionError, PublisherError) as exc:
        raise RetainedPublisherError("retained source unavailable") from exc
    if not hmac.compare_digest(hashlib.sha256(_canonical(manifest)).hexdigest(),
                               manifest_sha256):
        raise RetainedPublisherError("retained manifest differs from external pin")
    if not hmac.compare_digest(hashlib.sha256(archive).hexdigest(), artifact_sha256):
        raise RetainedPublisherError("retained artifact changed")
    with tempfile.TemporaryDirectory(prefix="sf-retained-review-") as tmp:
        consumed = Path(tmp) / "exact-retained.zip"
        consumed.write_bytes(archive)
        if hashlib.sha256(consumed.read_bytes()).hexdigest() != artifact_sha256:
            raise RetainedPublisherError("private copy changed")
        proof = authenticate_publisher(
            consumed, release_pin, policy, policy_sha256, attestation,
            verifier, trusted_root, minimum_release_epoch=minimum_release_epoch,
            today=today,
        )
    if (type(proof) is not dict
            or proof.get("status") != "verified-by-operator-pinned-cli"
            or proof.get("artifactSha256") != artifact_sha256
            or proof.get("policySha256") != policy_sha256
            or proof.get("sourceCommit") != manifest["sourceCommit"]
            or proof.get("sourceTree") != manifest["sourceTree"]
            or proof.get("independentPolicyCustodyVerified") is not False
            or proof.get("publisherAuthenticityQualified") is not False
            or proof.get("installationAuthorized") is not False
            or proof.get("releaseQualified") is not False
            or proof.get("accepted") is not False):
        raise RetainedPublisherError("contradictory or unsafe publisher observation")
    return {
        "schemaVersion": 1, "kind": "sf-pq07p-retained-publisher-no-go",
        "sourceCommit": manifest["sourceCommit"],
        "sourceTree": manifest["sourceTree"],
        "artifactSha256": artifact_sha256,
        "manifestSha256": manifest_sha256,
        "policySha256": policy_sha256,
        "publisherAttestationSha256": proof.get("attestationSha256"),
        "exactRetainedBytesObserved": True,
        "independentRetentionCustodyVerified": False,
        "independentPolicyCustodyVerified": False,
        "installationAuthorized": False, "releaseQualified": False,
        "productionQualified": False, "accepted": False,
        "status": "BLOCKED-external-qualification",
    }
