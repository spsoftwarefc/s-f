"""PQ-01A: bounded, read-only publisher-attestation verifier adapter.

This adapter invokes an operator-pinned GitHub CLI verifier against retained
attestation evidence. The caller must independently authenticate the policy
digest, verifier binary and trusted root. It never issues installation grants.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

from .distribution import (
    DistributionError, MAX_BUNDLE, MAX_METADATA, _canonical, _read_json,
    verify_bytes,
)

POLICY_KEYS = frozenset({
    "schemaVersion", "kind", "repository", "signerWorkflow", "signerDigest",
    "sourceCommit", "sourceTree", "sourceRef", "artifactSha256", "releaseId",
    "releaseEpoch", "verifierSha256", "trustedRootSha256", "expiresOn",
})
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
WORKFLOW = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/\.github/workflows/[A-Za-z0-9_.-]+\.ya?ml\Z")
REF = re.compile(r"refs/(?:heads|tags)/[A-Za-z0-9][A-Za-z0-9._/-]*\Z")
RELEASE = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{1,127}\Z")
MAX_ATTESTATION = 2 * 1024 * 1024
MAX_ROOT = 2 * 1024 * 1024
MAX_EXECUTABLE = 250 * 1024 * 1024
MAX_OUTPUT = 1024 * 1024


class PublisherError(ValueError):
    """An untrusted, unsupported or unavailable publisher verification input."""


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hex(value: object, pattern: re.Pattern[str], label: str) -> str:
    if type(value) is not str or not pattern.fullmatch(value):
        raise PublisherError(f"invalid {label}")
    return value


def _ref(value: object) -> str:
    if (type(value) is not str or not REF.fullmatch(value)
            or any(s in value for s in ("..", "//", "@{", "\\", " "))):
        raise PublisherError("invalid source ref")
    return value


def _policy(raw: bytes, expected_sha256: str, *, today: date | None = None) -> dict:
    _hex(expected_sha256, HEX64, "operator-provided policy digest")
    if _digest(raw) != expected_sha256:
        raise PublisherError("operator-pinned policy digest mismatch")
    try:
        data = _read_json(raw, "publisher policy")
    except DistributionError as exc:
        raise PublisherError("invalid publisher policy JSON") from exc
    if raw != _canonical(data) or set(data) != POLICY_KEYS:
        raise PublisherError("noncanonical or unsupported publisher policy")
    if type(data["schemaVersion"]) is not int or data["schemaVersion"] != 1:
        raise PublisherError("unsupported publisher policy schema")
    if data["kind"] != "sf-github-public-publisher-policy":
        raise PublisherError("unsupported publisher policy kind")
    if type(data["repository"]) is not str or not REPO.fullmatch(data["repository"]):
        raise PublisherError("invalid repository")
    if (type(data["signerWorkflow"]) is not str
            or not WORKFLOW.fullmatch(data["signerWorkflow"])
            or not data["signerWorkflow"].startswith(data["repository"] + "/")):
        raise PublisherError("unexpected signer workflow")
    _hex(data["signerDigest"], HEX40, "signer revision")
    _hex(data["sourceCommit"], HEX40, "source revision")
    _hex(data["sourceTree"], HEX40, "source tree")
    _hex(data["artifactSha256"], HEX64, "artifact digest")
    _hex(data["verifierSha256"], HEX64, "verifier digest")
    _hex(data["trustedRootSha256"], HEX64, "trusted root digest")
    _ref(data["sourceRef"])
    if type(data["releaseId"]) is not str or not RELEASE.fullmatch(data["releaseId"]):
        raise PublisherError("invalid release ID")
    if type(data["releaseEpoch"]) is not int or not 1 <= data["releaseEpoch"] <= 2**53:
        raise PublisherError("invalid release epoch")
    if type(data["expiresOn"]) is not str or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", data["expiresOn"]):
        raise PublisherError("invalid policy expiry")
    try:
        expiry = date.fromisoformat(data["expiresOn"])
    except ValueError as exc:
        raise PublisherError("invalid policy expiry") from exc
    if expiry < (today or datetime.now(timezone.utc).date()):
        raise PublisherError("publisher policy expired")
    return data


def _read_regular(path: Path, max_size: int, label: str) -> bytes:
    if not path.is_absolute() or path.is_symlink():
        raise PublisherError(f"unsafe {label} path")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= max_size:
                raise PublisherError(f"missing or oversized {label}")
            data = stream.read(max_size + 1)
            if len(data) != info.st_size:
                raise PublisherError(f"changed or oversized {label}")
            return data
    except (OSError, OverflowError) as exc:
        raise PublisherError(f"unavailable {label}") from exc


def _copy_pinned(src: Path, dst: Path, expected_digest: str,
                 maximum: int, label: str, executable: bool = False) -> None:
    # Copy then verify *the executable bytes to be run*, not just their old path.
    if not src.is_absolute() or src.is_symlink():
        raise PublisherError(f"unsafe {label} path")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        source_fd = os.open(src, flags)
        with os.fdopen(source_fd, "rb") as source:
            info = os.fstat(source.fileno())
            if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= maximum:
                raise PublisherError(f"missing or oversized {label}")
            # Destination is exclusively created in the private temporary directory.
            output_fd = os.open(dst, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(output_fd, "wb") as target:
                h = hashlib.sha256()
                remaining = info.st_size
                while remaining:
                    chunk = source.read(min(1024 * 1024, remaining))
                    if not chunk:
                        raise PublisherError(f"truncated {label}")
                    remaining -= len(chunk)
                    target.write(chunk)
                    h.update(chunk)
                if source.read(1):
                    raise PublisherError(f"changed {label}")
                target.flush()
                os.fsync(target.fileno())
            if h.hexdigest() != expected_digest:
                raise PublisherError(f"operator-pinned {label} digest mismatch")
            if executable:
                os.chmod(dst, 0o700)
    except (OSError, OverflowError) as exc:
        raise PublisherError(f"unavailable {label}") from exc


def authenticate_publisher(
    artifact: Path, release_pin: Path, policy_path: Path,
    expected_policy_sha256: str, attestation_path: Path,
    verifier_path: Path, trusted_root_path: Path,
    *, minimum_release_epoch: int,
    today: date | None = None,
) -> dict:
    """Verify retained evidence with a separately provisioned/pinned gh binary.

    Successful return is a conditional technical observation; the function
    cannot prove how an operator originally obtained the policy digest.
    """
    if (type(minimum_release_epoch) is not int or minimum_release_epoch < 1
            or minimum_release_epoch > 2**53):
        raise PublisherError("invalid minimum release epoch")
    policy_bytes = _read_regular(policy_path, MAX_METADATA, "publisher policy")
    policy = _policy(policy_bytes, expected_policy_sha256, today=today)
    if policy["releaseEpoch"] < minimum_release_epoch:
        raise PublisherError("unauthorized release downgrade")
    archive = _read_regular(artifact, MAX_BUNDLE, "factory artifact")
    if _digest(archive) != policy["artifactSha256"]:
        raise PublisherError("artifact differs from operator trust policy")
    try:
        pin_bytes = _read_regular(release_pin, MAX_METADATA, "external release pin")
        pin = _read_json(pin_bytes, "external release pin")
        checked = verify_bytes(archive, pin, today=today)
    except DistributionError as exc:
        raise PublisherError("factory artifact or release pin rejected") from exc
    if (pin["bundleSha256"] != policy["artifactSha256"]
            or pin["sourceCommit"] != policy["sourceCommit"]
            or pin["sourceTree"] != policy["sourceTree"]
            or pin["releaseId"] != policy["releaseId"]):
        raise PublisherError("release pin disagrees with independently pinned policy")
    attestation = _read_regular(attestation_path, MAX_ATTESTATION, "attestation")
    root = _read_regular(trusted_root_path, MAX_ROOT, "trusted root")
    if _digest(root) != policy["trustedRootSha256"]:
        raise PublisherError("operator-pinned trusted root digest mismatch")
    with tempfile.TemporaryDirectory(prefix="sf-publisher-") as temp:
        cwd = Path(temp)
        verifier = cwd / ("verifier.exe" if os.name == "nt" else "verifier")
        artifact_copy = cwd / "artifact.zip"
        bundle_file = cwd / "attestation.jsonl"
        root_file = cwd / "trusted-root.jsonl"
        _copy_pinned(verifier_path, verifier, policy["verifierSha256"],
                     MAX_EXECUTABLE, "verifier", executable=True)
        artifact_copy.write_bytes(archive)
        bundle_file.write_bytes(attestation)
        root_file.write_bytes(root)
        # Do not use a shell, ambient GitHub token, configuration, user home or
        # candidate-owned command arguments. These flags enforce certificate
        # identity in gh; parsed statement contents alone are not issuer proof.
        args = [
            str(verifier), "attestation", "verify", str(artifact_copy),
            "--bundle", str(bundle_file),
            "--custom-trusted-root", str(root_file),
            "--repo", policy["repository"],
            "--signer-workflow", policy["signerWorkflow"],
            "--signer-digest", policy["signerDigest"],
            "--source-digest", policy["sourceCommit"],
            "--source-ref", policy["sourceRef"],
            "--cert-oidc-issuer", "https://token.actions.githubusercontent.com",
            "--predicate-type", "https://slsa.dev/provenance/v1",
            "--format", "json",
        ]
        env = {
            "HOME": str(cwd), "GH_CONFIG_DIR": str(cwd),
            "GH_PROMPT_DISABLED": "1", "GIT_TERMINAL_PROMPT": "0",
            "LC_ALL": "C",
            "PATH": os.environ.get("SystemRoot", "") if os.name == "nt" else "/usr/bin:/bin",
        }
        try:
            completed = subprocess.run(
                args, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                timeout=30, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise PublisherError("pinned verifier unavailable") from exc
        if completed.returncode or len(completed.stdout) > MAX_OUTPUT:
            raise PublisherError("pinned verifier rejected attestation")
        try:
            observations = json.loads(completed.stdout)
        except (ValueError, UnicodeError, RecursionError) as exc:
            raise PublisherError("invalid verifier result") from exc
        if type(observations) is not list or not observations or len(observations) > 16:
            raise PublisherError("missing verified provenance statement")
        matched = False
        for row in observations:
            if type(row) is not dict or "verificationResult" not in row:
                raise PublisherError("malformed verifier result")
            result = row["verificationResult"]
            if type(result) is not dict or type(result.get("statement")) is not dict:
                raise PublisherError("malformed verified statement")
            statement = result["statement"]
            if statement.get("predicateType") != "https://slsa.dev/provenance/v1":
                continue
            subjects = statement.get("subject")
            if type(subjects) is not list or len(subjects) > 64:
                raise PublisherError("malformed artifact subjects")
            for subject in subjects:
                if (type(subject) is dict and type(subject.get("digest")) is dict
                        and subject["digest"].get("sha256") == policy["artifactSha256"]):
                    matched = True
        if not matched:
            raise PublisherError("verified statement does not bind artifact")
    return {
        "schemaVersion": 1, "kind": "sf-pq01a-publisher-observation",
        "status": "verified-by-operator-pinned-cli",
        "policySha256": expected_policy_sha256,
        "verifierSha256": policy["verifierSha256"],
        "trustedRootSha256": policy["trustedRootSha256"],
        "attestationSha256": _digest(attestation),
        "artifactSha256": policy["artifactSha256"],
        "repository": policy["repository"], "sourceCommit": policy["sourceCommit"],
        "sourceTree": policy["sourceTree"], "sourceRef": policy["sourceRef"],
        "signerWorkflow": policy["signerWorkflow"],
        "releaseEpoch": policy["releaseEpoch"],
        "offlineVerifierReportedValid": True,
        "independentPolicyCustodyVerified": False,
        "publisherAuthenticityQualified": False,
        "installationAuthorized": False, "releaseQualified": False,
        "accepted": False, "legacyPinnedLock": checked["lock"],
    }
