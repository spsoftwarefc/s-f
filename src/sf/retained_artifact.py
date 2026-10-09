"""PQ-03: local exact-byte retained build records, not signed provenance.

A declared manifest is candidate data; trusted builder identity and independent
retention custody require later external verification.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import date, datetime, timezone
from pathlib import Path

from .distribution import MAX_BUNDLE
from .publisher import _read_regular

HASH = re.compile(r"[0-9a-f]{64}\Z")
GIT = re.compile(r"[0-9a-f]{40}\Z")
IDENT = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,127}\Z")
KEYS = {"schemaVersion", "kind", "releaseId", "artifactSha256", "sourceCommit",
        "sourceTree", "toolchainSha256", "sbomSha256", "provenanceSha256", "retainUntil"}


class RetentionError(ValueError):
    """Untrusted or unavailable local retained artifact."""


def _canonical(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode()


def _validate(manifest: dict, *, today: date | None = None) -> None:
    if type(manifest) is not dict or set(manifest) != KEYS or (
            type(manifest["schemaVersion"]) is not int
            or manifest["schemaVersion"] != 1
            or manifest["kind"] != "sf-reference-retained-build"):
        raise RetentionError("unsupported retained build identity")
    if type(manifest["releaseId"]) is not str or not IDENT.fullmatch(manifest["releaseId"]):
        raise RetentionError("invalid release identifier")
    for name in ("artifactSha256", "toolchainSha256", "sbomSha256", "provenanceSha256"):
        if type(manifest[name]) is not str or not HASH.fullmatch(manifest[name]):
            raise RetentionError("invalid retained digest: " + name)
    for name in ("sourceCommit", "sourceTree"):
        if type(manifest[name]) is not str or not GIT.fullmatch(manifest[name]):
            raise RetentionError("invalid source identity")
    if type(manifest["retainUntil"]) is not str:
        raise RetentionError("invalid retention expiry")
    try:
        expires = date.fromisoformat(manifest["retainUntil"])
        if expires.isoformat() != manifest["retainUntil"]:
            raise ValueError("noncanonical date")
    except ValueError as exc:
        raise RetentionError("invalid retention expiry") from exc
    if expires < (today or datetime.now(timezone.utc).date()):
        raise RetentionError("retention has expired")


def _store(directory: Path) -> None:
    if not directory.is_absolute() or directory.is_symlink() or not directory.is_dir():
        raise RetentionError("retention directory must preexist and not be a symlink")


def _paths(directory: Path, sha256: str) -> tuple[Path, Path]:
    return (directory / (sha256 + ".zip"), directory / (sha256 + ".manifest.json"))


def _read_manifest(path: Path) -> dict:
    raw = _read_regular(path, 65536, "retained manifest")
    try:
        def unique(pairs):
            out = {}
            for key, value in pairs:
                if key in out:
                    raise RetentionError("duplicate manifest key")
                out[key] = value
            return out
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise RetentionError("invalid retained manifest") from exc
    if type(value) is not dict or _canonical(value) != raw:
        raise RetentionError("noncanonical retained manifest")
    return value


def read_retained(directory: Path, artifact_sha256: str, *,
                  today: date | None = None) -> tuple[dict, bytes]:
    """Return retained existing bytes; never execute or rebuild source."""
    _store(directory)
    if type(artifact_sha256) is not str or not HASH.fullmatch(artifact_sha256):
        raise RetentionError("invalid lookup digest")
    artifact_path, manifest_path = _paths(directory, artifact_sha256)
    manifest = _read_manifest(manifest_path)
    _validate(manifest, today=today)
    raw = _read_regular(artifact_path, MAX_BUNDLE, "retained artifact")
    if (hashlib.sha256(raw).hexdigest() != artifact_sha256
            or manifest["artifactSha256"] != artifact_sha256):
        raise RetentionError("retained bytes differ from manifest")
    return manifest, raw


def _write_once(path: Path, data: bytes) -> None:
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "wb") as out:
        out.write(data)
        out.flush()
        os.fsync(out.fileno())


def stage_retained(source: Path, directory: Path, manifest: dict, *,
                   today: date | None = None) -> dict:
    """Write once to explicit local store; conflicting existing bytes block."""
    _store(directory)
    _validate(manifest, today=today)
    archive = _read_regular(source, MAX_BUNDLE, "source artifact")
    digest = hashlib.sha256(archive).hexdigest()
    if digest != manifest["artifactSha256"]:
        raise RetentionError("source bytes disagree with declared digest")
    artifact_path, manifest_path = _paths(directory, digest)
    wanted = _canonical(manifest)
    if artifact_path.exists() or manifest_path.exists():
        current, content = read_retained(directory, digest, today=today)
        if current != manifest or content != archive:
            raise RetentionError("conflicting existing retained identity")
        return {"status": "already-retained", "artifactSha256": digest,
                "signedProvenanceVerified": False, "independentCustodyVerified": False}
    try:
        _write_once(artifact_path, archive)
        _write_once(manifest_path, wanted)
        if os.name == "posix":
            fd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
    except (OSError, OverflowError) as exc:
        raise RetentionError("unable to complete retained bundle commit") from exc
    # A local exclusive-create is NOT a WORM/immutable independent store.
    read_retained(directory, digest, today=today)
    return {"status": "retained-locally", "artifactSha256": digest,
            "signedProvenanceVerified": False, "independentCustodyVerified": False}
