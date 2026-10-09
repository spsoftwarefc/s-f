"""PQ-01B: optional authenticated *apply* boundary for SF-13I portable bytes.

The caller must provision the policy digest, verifier/root, and minimum epoch
independently of this candidate. This module cannot prove that custody or the
freshness of offline evidence. It never upgrades preview installation claims.
"""
from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

from . import pinned
from .publisher import (
    MAX_BUNDLE, PublisherError, _read_regular, authenticate_publisher,
)


def authenticated_apply(
    root: Path, profile: Path, plan: Path, *,
    mode: str, artifact: Path, trust: Path, lock: Path,
    release_pin: Path, policy: Path, expected_policy_sha256: str,
    attestation: Path, verifier: Path, trusted_root: Path,
    minimum_release_epoch: int, ack_manual: bool = False,
) -> dict:
    """Check publisher identity and consume only a byte-matched private copy.

    A caller must separately authorize the filesystem effect and establish
    independent policy custody. Recovery and removal need their own gates.
    """
    if mode not in ("integrate", "upgrade"):
        raise PublisherError("publisher apply requires integrate or upgrade")
    proof = authenticate_publisher(
        artifact, release_pin, policy, expected_policy_sha256,
        attestation, verifier, trusted_root,
        minimum_release_epoch=minimum_release_epoch,
    )
    if (
        type(proof) is not dict
        or proof.get("status") != "verified-by-operator-pinned-cli"
        or proof.get("policySha256") != expected_policy_sha256
        or type(proof.get("artifactSha256")) is not str
        or proof.get("installationAuthorized") is not False
        or proof.get("releaseQualified") is not False
        or proof.get("accepted") is not False
    ):
        raise PublisherError("invalid or authority-confused publisher observation")
    # A mutable source can change after the verifier subprocess exits. Never
    # let the installer re-read that source; copy, hash and pin *consumed* bytes.
    raw = _read_regular(artifact, MAX_BUNDLE, "factory artifact")
    if hashlib.sha256(raw).hexdigest() != proof["artifactSha256"]:
        raise PublisherError("factory artifact changed since publisher verification")
    with tempfile.TemporaryDirectory(prefix="sf-publisher-apply-") as directory:
        copied = Path(directory) / "verified.zip"
        copied.write_bytes(raw)
        if hashlib.sha256(copied.read_bytes()).hexdigest() != proof["artifactSha256"]:
            raise PublisherError("private archive copy disagrees with publisher digest")
        receipt = pinned.apply(
            root, profile, plan, mode=mode, bundle=copied, trust=trust,
            lock=lock, ack_manual=ack_manual,
        )
    if type(receipt) is not dict:
        raise PublisherError("invalid installed distribution receipt")
    return {
        **receipt,
        "publisherVerificationObserved": True,
        "publisherEvidenceSha256": proof.get("attestationSha256"),
        "publisherPolicySha256": expected_policy_sha256,
        # The local tool cannot establish independent policy custody, current
        # revocation, authenticated grants, or recovery-time reauthorization.
        "independentPolicyCustodyVerified": False,
        "productionQualified": False,
        "releaseQualified": False,
    }
