"""PQ-07G: bounded local intake for raw campaign evidence, NOT authentication.

The expected manifest digest and candidate identifiers must arrive through a
separate operator channel. Checking bytes cannot establish publisher identity,
provider facts, policy custody, effect authority, or remote target behavior.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import stat
from pathlib import Path

from .production_dossier import REQUIRED_CLAIMS

GIT = re.compile(r"[0-9a-f]{40}\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")
IDENT = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,127}\Z")
FIELDS = {"schemaVersion", "kind", "sourceCommit", "sourceTree", "artifactSha256",
          "policySha256", "profile", "cases"}
PROFILE = {"scopeId", "platform", "adapter", "environment"}
CASE = {"claim", "positivePath", "positiveSha256", "negativePath",
        "negativeSha256", "issuer"}
MAX_MANIFEST = 128 * 1024
MAX_CASE_BYTES = 2 * 1024 * 1024


class CampaignIntakeError(ValueError):
    """A candidate binding, manifest or raw file failed safe inspection."""


def _check(value: object, pattern: re.Pattern[str], name: str) -> str:
    if type(value) is not str or pattern.fullmatch(value) is None:
        raise CampaignIntakeError("invalid " + name)
    return value


def _canonical(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=True,
                       allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")


def _unique(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise CampaignIntakeError("duplicate manifest key")
        result[k] = v
    return result


def _safe_path(raw: str) -> Path:
    if type(raw) is not str or len(raw) > 4096 or "\x00" in raw:
        raise CampaignIntakeError("invalid evidence path")
    path = Path(raw)
    if not path.is_absolute() or ".." in path.parts:
        raise CampaignIntakeError("evidence path must be absolute without traversal")
    # Checking all ancestor components rejects a common symlink indirection,
    # but this is NOT an atomic untrusted-filesystem sandbox.
    for part in (path, *path.parents):
        if part.is_symlink():
            raise CampaignIntakeError("symlink evidence path")
    return path


def _read(path: Path, limit: int) -> tuple[bytes, tuple[int, int]] | None:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise CampaignIntakeError("unavailable raw evidence") from exc
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= limit:
            raise CampaignIntakeError("invalid raw evidence size or file type")
        raw = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
        if len(raw) != info.st_size or (info.st_size, info.st_mtime_ns) != (
                after.st_size, after.st_mtime_ns):
            raise CampaignIntakeError("raw evidence changed while reading")
        return raw, (info.st_dev, info.st_ino)


def inspect_campaign(
    manifest_path: Path, *, expected_manifest_sha256: str,
    expected_source_commit: str, expected_source_tree: str,
    expected_artifact_sha256: str, expected_policy_sha256: str,
) -> dict:
    """Inventory pinned raw proof bytes; never authenticate a supplied issuer.

    Missing files are reported as incomplete; an observed file with unexpected
    bytes is rejected. Callers must not infer release/effect permission.
    """
    for value, pattern, name in (
        (expected_manifest_sha256, HASH, "manifest digest"),
        (expected_source_commit, GIT, "source commit"),
        (expected_source_tree, GIT, "source tree"),
        (expected_artifact_sha256, HASH, "artifact digest"),
        (expected_policy_sha256, HASH, "policy digest"),
    ):
        _check(value, pattern, name)
    manifest_read = _read(_safe_path(str(manifest_path)), MAX_MANIFEST)
    if manifest_read is None:
        raise CampaignIntakeError("missing operator-pinned manifest")
    raw, manifest_identity = manifest_read
    if not hmac.compare_digest(hashlib.sha256(raw).hexdigest(), expected_manifest_sha256):
        raise CampaignIntakeError("operator manifest digest mismatch")
    try:
        document = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise CampaignIntakeError("invalid manifest JSON") from exc
    if type(document) is not dict or set(document) != FIELDS or raw != _canonical(document):
        raise CampaignIntakeError("noncanonical or unsupported manifest fields")
    if type(document["schemaVersion"]) is not int or document["schemaVersion"] != 1 or (
            document["kind"] != "sf-pq07g-raw-evidence-intake"):
        raise CampaignIntakeError("unsupported manifest version or kind")
    for key, expected in (
        ("sourceCommit", expected_source_commit),
        ("sourceTree", expected_source_tree),
        ("artifactSha256", expected_artifact_sha256),
        ("policySha256", expected_policy_sha256),
    ):
        if document[key] != expected:
            raise CampaignIntakeError("campaign exact candidate/policy mismatch")
    profile = document["profile"]
    if type(profile) is not dict or set(profile) != PROFILE:
        raise CampaignIntakeError("invalid campaign profile")
    for name, value in profile.items():
        _check(value, IDENT, name)
    if (profile["platform"], profile["adapter"], profile["environment"]) != (
            "linux", "disposable-single-host", "test"):
        raise CampaignIntakeError("unsupported live qualification profile")
    cases = document["cases"]
    if type(cases) is not list or len(cases) > len(REQUIRED_CLAIMS):
        raise CampaignIntakeError("invalid campaign cases")
    observed = {}
    used_files = {manifest_identity}
    for case in cases:
        if type(case) is not dict or set(case) != CASE:
            raise CampaignIntakeError("unsupported campaign case")
        claim = case["claim"]
        if type(claim) is not str or claim not in REQUIRED_CLAIMS or claim in observed:
            raise CampaignIntakeError("duplicate or unknown campaign claim")
        _check(case["issuer"], IDENT, "issuer label")
        for name in ("positiveSha256", "negativeSha256"):
            _check(case[name], HASH, name)
        if case["positiveSha256"] == case["negativeSha256"]:
            raise CampaignIntakeError("positive and negative cases have same expected bytes")
        status = []
        for prefix in ("positive", "negative"):
            path = _safe_path(case[prefix + "Path"])
            read = _read(path, MAX_CASE_BYTES)
            if read is None:
                status.append("missing")
                continue
            body, identity = read
            if identity in used_files:
                raise CampaignIntakeError("aliased or reused raw evidence file")
            used_files.add(identity)
            digest = hashlib.sha256(body).hexdigest()
            if not hmac.compare_digest(digest, case[prefix + "Sha256"]):
                raise CampaignIntakeError("raw evidence digest mismatch")
            status.append("present-unverified")
        observed[claim] = status
    report = [
        {"claim": claim, "positive": observed.get(claim, ["missing", "missing"])[0],
         "negative": observed.get(claim, ["missing", "missing"])[1]}
        for claim in REQUIRED_CLAIMS
    ]
    return {
        "schemaVersion": 1, "kind": "sf-pq07g-raw-evidence-gap-report",
        "sourceCommit": expected_source_commit,
        "sourceTree": expected_source_tree,
        "artifactSha256": expected_artifact_sha256,
        "policySha256": expected_policy_sha256,
        "manifestSha256": expected_manifest_sha256,
        "rawCasesPresent": all(r["positive"] == r["negative"] == "present-unverified"
                               for r in report),
        "claimCases": report,
        "candidateIssuerLabelsAuthenticated": False,
        "independentPolicyCustodyVerified": False,
        "externalEvidenceAuthenticated": False,
        "releaseAuthorized": False, "publishAuthorized": False,
        "adopterPilotAuthorized": False, "productionQualified": False,
        "status": "BLOCKED-external-qualification",
    }
