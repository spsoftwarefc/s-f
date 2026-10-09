"""PQ-07D: independently rehash existing local retained build support bytes.

Byte integrity is NOT provenance authentication or independent retention.
"""
from __future__ import annotations

import hashlib
import hmac
import re
from pathlib import Path

from .publisher import PublisherError, _read_regular
from .retained_artifact import read_retained, RetentionError

SHA = re.compile(r"[0-9a-f]{64}\Z")
MAX_PROOF_BYTES = 2 * 1024 * 1024


class ArtifactAuditError(ValueError):
    """Mismatch, missing local evidence or unsafe candidate inputs."""


def audit_retained_inputs(
    store: Path, artifact_sha256: str, expected_manifest_sha256: str,
    *, sbom_path: Path, provenance_path: Path, toolchain_lock_path: Path,
) -> dict:
    for label, value in (("artifact", artifact_sha256),
                         ("manifest", expected_manifest_sha256)):
        if type(value) is not str or SHA.fullmatch(value) is None:
            raise ArtifactAuditError("invalid " + label + " expected digest")
    files = (sbom_path, provenance_path, toolchain_lock_path)
    if any(not isinstance(p, Path) or not p.is_absolute() for p in files):
        raise ArtifactAuditError("all independent file paths must be absolute")
    if len({p.resolve(strict=False) for p in files}) != len(files):
        raise ArtifactAuditError("evidence roles must not alias")
    try:
        manifest_raw = _read_regular(store / (artifact_sha256 + ".manifest.json"),
                                     MAX_PROOF_BYTES, "retained manifest")
        if not hmac.compare_digest(
                hashlib.sha256(manifest_raw).hexdigest(), expected_manifest_sha256):
            raise ArtifactAuditError("manifest differs from independently pinned digest")
        manifest, archive = read_retained(store, artifact_sha256)
        for label, path, field in (
            ("SBOM", sbom_path, "sbomSha256"),
            ("provenance", provenance_path, "provenanceSha256"),
            ("toolchain lock", toolchain_lock_path, "toolchainSha256"),
        ):
            raw = _read_regular(path, MAX_PROOF_BYTES, label)
            if not hmac.compare_digest(hashlib.sha256(raw).hexdigest(), manifest[field]):
                raise ArtifactAuditError("retained " + label + " does not match declared bytes")
    except (RetentionError, PublisherError) as exc:
        raise ArtifactAuditError("retention bytes unavailable") from exc
    return {
        "schemaVersion": 1, "kind": "sf-pq07d-retained-byte-audit",
        "artifactSha256": artifact_sha256, "manifestSha256": expected_manifest_sha256,
        "bytesRechecked": True, "artifactSize": len(archive),
        "sbomByteMatched": True, "provenanceByteMatched": True,
        "toolchainLockByteMatched": True,
        "independentPublisherCustodyVerified": False,
        "signedProvenanceVerified": False, "releaseQualified": False,
        "accepted": False, "productionQualified": False,
    }
