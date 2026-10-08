"""SF-14: offline source, artifact, destination and recovery release planning.

This module constructs no deployment and authenticates no approval issuer.
External digest-pinned approval identity remains conditional on operator custody.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

MAX_METADATA = 1024 * 1024
MAX_ARTIFACT = 64 * 1024 * 1024
MAX_PLAN_FILE = 4 * 1024 * 1024
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SHA64 = re.compile(r"[0-9a-f]{64}\Z")
IDENT = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,127}\Z")
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
REQ_KEYS = {"schemaVersion", "kind", "source", "artifact", "ci", "destination",
            "authorization", "migration", "recovery"}
PIN_KEYS = {"schemaVersion", "kind", "requestSha256", "sourceCommit",
            "sourceTree", "ciSha256", "artifactSha256", "destination",
            "grantId", "expiresOn", "migrationSha256", "recoverySha256"}


class ReleasePlanError(ValueError):
    """Malformed or nonmatching release-planning inputs."""


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _unique(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ReleasePlanError("duplicate release-plan JSON key")
        result[key] = value
    return result


def _regular(path: Path, size_limit: int, label: str) -> bytes:
    if (path.is_symlink() or not path.is_file() or path.stat().st_size > size_limit
            or path.stat().st_size == 0):
        raise ReleasePlanError(f"{label}: must be a nonempty, bounded regular file")
    return path.read_bytes()


def _load(raw: bytes, label: str) -> dict:
    if len(raw) > MAX_METADATA:
        raise ReleasePlanError(f"{label}: oversized JSON")
    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique)
    except ReleasePlanError:
        raise
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ReleasePlanError(f"{label}: invalid JSON") from exc
    if type(data) is not dict:
        raise ReleasePlanError(f"{label}: expected object")
    return data


def _fields(value: Any, expected: set[str], label: str) -> dict:
    if type(value) is not dict or set(value) != expected:
        raise ReleasePlanError(f"{label}: unknown or missing fields")
    return value


def _id(value: Any, label: str) -> str:
    if type(value) is not str or not IDENT.fullmatch(value):
        raise ReleasePlanError(f"{label}: invalid identity")
    return value


def _sha(value: Any, label: str, *, git: bool = False) -> str:
    if type(value) is not str or not (SHA40 if git else SHA64).fullmatch(value):
        raise ReleasePlanError(f"{label}: invalid digest")
    return value


def _date(value: Any, label: str, current: date) -> str:
    if type(value) is not str or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ReleasePlanError(f"{label}: invalid date")
    try:
        expires = date.fromisoformat(value)
    except ValueError as exc:
        raise ReleasePlanError(f"{label}: invalid date") from exc
    if expires < current:
        raise ReleasePlanError(f"{label}: expired")
    return value


def _path(value: Any, label: str) -> str:
    if (type(value) is not str or not value or len(value) > 300
            or value.startswith(("/", "\\")) or "\\" in value or ":" in value
            or value != value.strip() or any(x in ("", ".", "..", ".git")
                or x.endswith((" ", ".")) for x in value.split("/"))):
        raise ReleasePlanError(f"{label}: noncanonical relative path")
    return value


def _git(root: Path, *parts: str) -> bytes:
    try:
        run = subprocess.run(["git", "-C", str(root), "-c", "core.fsmonitor=false",
                              "-c", "core.untrackedCache=false", "--no-pager", *parts],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15,
                             env={**os.environ, "GIT_TERMINAL_PROMPT": "0",
                                  "GIT_OPTIONAL_LOCKS": "0"}, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ReleasePlanError("Git source identity unavailable") from exc
    if run.returncode:
        raise ReleasePlanError("Git source identity unavailable: " + parts[0])
    return run.stdout


def _source(root: Path, request: dict) -> None:
    if root.is_symlink() or not root.is_dir():
        raise ReleasePlanError("release source must be a real worktree directory")
    expected = _fields(request, {"repository", "commit", "tree"}, "source")
    if (type(expected["repository"]) is not str or not REPOSITORY.fullmatch(expected["repository"])
            or any(s in (".", "..") for s in expected["repository"].split("/"))):
        raise ReleasePlanError("invalid source repository identity")
    _sha(expected["commit"], "source.commit", git=True)
    _sha(expected["tree"], "source.tree", git=True)
    if Path(os.fsdecode(_git(root, "rev-parse", "--show-toplevel").strip())).resolve() != root:
        raise ReleasePlanError("source path is not Git worktree root")
    commit = _git(root, "rev-parse", "HEAD").decode("ascii").strip()
    tree = _git(root, "rev-parse", "HEAD^{tree}").decode("ascii").strip()
    if commit != expected["commit"] or tree != expected["tree"]:
        raise ReleasePlanError("source commit/tree mismatches accepted identity")
    if _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all"):
        raise ReleasePlanError("release source worktree is dirty")


def _tracked_plan(root: Path, value: Any, label: str) -> tuple[str, str]:
    item = _fields(value, {"path", "sha256", "disposition"}, label)
    path = _path(item["path"], label)
    _sha(item["sha256"], label)
    if item["disposition"] not in ("no-change", "forward", "rollback", "restore"):
        raise ReleasePlanError(f"{label}: unsupported recovery/migration disposition")
    dest = root / path
    if not dest.resolve(strict=False).is_relative_to(root):
        raise ReleasePlanError(f"{label}: path escapes source root")
    raw = _regular(dest, MAX_PLAN_FILE, label)
    # The file must be committed in the accepted source tree, not a local
    # replacement that happens to share an operator-authored request.
    if _git(root, "show", "HEAD:" + path) != raw:
        raise ReleasePlanError(f"{label}: disk plan differs from accepted source")
    if _hash(raw) != item["sha256"]:
        raise ReleasePlanError(f"{label}: committed plan digest differs")
    return path, item["sha256"]


def _request(raw: bytes, current: date) -> dict:
    q = _fields(_load(raw, "release request"), REQ_KEYS, "release request")
    if type(q["schemaVersion"]) is not int or q["schemaVersion"] != 1 or q["kind"] != "sf-release-plan-request":
        raise ReleasePlanError("unsupported release request schema")
    source = _fields(q["source"], {"repository", "commit", "tree"}, "source")
    _sha(source["commit"], "source.commit", git=True)
    _sha(source["tree"], "source.tree", git=True)
    artifact = _fields(q["artifact"], {"sha256", "kind"}, "artifact")
    _sha(artifact["sha256"], "artifact.sha256")
    _id(artifact["kind"], "artifact.kind")
    ci = _fields(q["ci"], {"receiptSha256", "runId", "attempt"}, "CI")
    _sha(ci["receiptSha256"], "ci.receiptSha256")
    if any(type(ci[x]) is not int or ci[x] <= 0 for x in ("runId", "attempt")):
        raise ReleasePlanError("CI run identity must be positive integers")
    destination = _fields(q["destination"], {"targetId", "environment", "adapter"}, "destination")
    for name in ("targetId", "environment", "adapter"):
        _id(destination[name], f"destination.{name}")
    auth = _fields(q["authorization"], {"principal", "grantId", "expiresOn"}, "authorization")
    for name in ("principal", "grantId"):
        _id(auth[name], "authorization." + name)
    _date(auth["expiresOn"], "authorization.expiresOn", current)
    for name in ("migration", "recovery"):
        _fields(q[name], {"path", "sha256", "disposition"}, name)
        _path(q[name]["path"], name)
        _sha(q[name]["sha256"], name)
    return q


def _pin(raw: bytes, request: dict, request_bytes: bytes, current: date) -> dict:
    p = _fields(_load(raw, "approved release pin"), PIN_KEYS, "approved release pin")
    if (type(p["schemaVersion"]) is not int or p["schemaVersion"] != 1
            or p["kind"] != "sf-externally-approved-release-pin"):
        raise ReleasePlanError("unsupported approved release pin")
    for field in ("requestSha256", "ciSha256", "artifactSha256", "migrationSha256", "recoverySha256"):
        _sha(p[field], "pin." + field)
    for field in ("sourceCommit", "sourceTree"):
        _sha(p[field], "pin." + field, git=True)
    _id(p["grantId"], "pin.grantId")
    _date(p["expiresOn"], "pin.expiresOn", current)
    d = _fields(p["destination"], {"targetId", "environment", "adapter"}, "pin.destination")
    for item in ("targetId", "environment", "adapter"):
        _id(d[item], "pin.destination." + item)
    expected = {
        "requestSha256": _hash(request_bytes),
        "sourceCommit": request["source"]["commit"],
        "sourceTree": request["source"]["tree"],
        "ciSha256": request["ci"]["receiptSha256"],
        "artifactSha256": request["artifact"]["sha256"],
        "destination": request["destination"],
        "grantId": request["authorization"]["grantId"],
        "expiresOn": request["authorization"]["expiresOn"],
        "migrationSha256": request["migration"]["sha256"],
        "recoverySha256": request["recovery"]["sha256"],
    }
    for field, expected_value in expected.items():
        if p[field] != expected_value:
            raise ReleasePlanError("external approval pin disagrees with release request: " + field)
    return p


def plan_release(root: Path, request_file: Path, artifact_file: Path,
                 ci_receipt_file: Path, approval_pin_file: Path,
                 *, today: date | None = None) -> dict:
    """Read-only exact-input plan; no release, auth, network or filesystem effects."""
    root = root.resolve(strict=True) if not root.is_symlink() else root
    current = today or datetime.now(timezone.utc).date()
    paths = (request_file, artifact_file, ci_receipt_file, approval_pin_file)
    if len({str(path.resolve(strict=False)) for path in paths}) != len(paths):
        raise ReleasePlanError("release-plan request, artifact, CI proof and approval pin must be distinct")
    request_raw = _regular(request_file, MAX_METADATA, "release request")
    request = _request(request_raw, current)
    _source(root, request["source"])
    for name in ("migration", "recovery"):
        _tracked_plan(root, request[name], name)
    artifact_digest = _hash(_regular(artifact_file, MAX_ARTIFACT, "artifact"))
    if artifact_digest != request["artifact"]["sha256"]:
        raise ReleasePlanError("artifact bytes do not match declared SHA-256")
    receipt_raw = _regular(ci_receipt_file, MAX_METADATA, "CI receipt")
    if _hash(receipt_raw) != request["ci"]["receiptSha256"]:
        raise ReleasePlanError("CI evidence bytes do not match declared digest")
    ci = _load(receipt_raw, "CI receipt")
    if (ci.get("schemaVersion") != 1 or ci.get("source") != "github"
            or ci.get("status") != "provider-metadata-verified"
            or ci.get("providerMetadataVerified") is not True
            or ci.get("accepted") is not False
            or ci.get("candidateSha") != request["source"]["commit"]
            or ci.get("runId") != request["ci"]["runId"]
            or ci.get("attempt") != request["ci"]["attempt"]):
        raise ReleasePlanError("CI receipt missing/mismatching source provider metadata")
    pin_raw = _regular(approval_pin_file, MAX_METADATA, "external approved release pin")
    _pin(pin_raw, request, request_raw, current)
    return {
        "schemaVersion": 1, "kind": "sf-offline-release-plan",
        "status": "matches-external-approval-pin-not-authenticated",
        "source": request["source"], "sourceCheckoutVerified": True,
        "artifact": {"kind": request["artifact"]["kind"], "sha256": artifact_digest},
        "ci": {"runId": ci["runId"], "attempt": ci["attempt"],
               "receiptSha256": _hash(receipt_raw),
               "providerMetadataClaimReverifiedLive": False},
        "destination": request["destination"],
        "authorization": request["authorization"],
        "migration": request["migration"], "recovery": request["recovery"],
        "requestSha256": _hash(request_raw), "externalApprovalPinSha256": _hash(pin_raw),
        "approvedReleaseOriginAuthenticated": False,
        "independentSourceAcceptanceVerified": False,
        "deploymentAuthorized": False, "artifactDeployed": False,
        "releaseQualified": False, "accepted": False, "readOnly": True,
    }
