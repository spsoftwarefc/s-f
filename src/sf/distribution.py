"""SF-13: deterministic source archive and externally pinned offline verification.

An archive's own manifest is not a trust anchor. Verification requires a trust
record separately provisioned through an authenticated operator channel.
No distribution, installation, release or merge is executed here.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import subprocess
import tempfile
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__

MAX_BUNDLE = 20 * 1024 * 1024
MAX_FILE = 2 * 1024 * 1024
MAX_FILES = 300
MAX_METADATA = 1024 * 1024
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
NAME = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{1,127}\Z")
VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9._-]+)?\Z")
PORTABLE_PREFIXES = ("src/sf/", ".agents/skills/factory-context/",
                     ".agents/skills/factory-implementation/", ".agents/skills/factory-review/")
PORTABLE_EXACT = frozenset({"pyproject.toml", "docs/factory/WORKFLOW.md",
                            "docs/factory/WORK_ORDER.md"})
MANDATORY = frozenset({"pyproject.toml", "src/sf/__init__.py", "src/sf/cli.py",
                       "docs/factory/WORKFLOW.md", "docs/factory/WORK_ORDER.md",
                       ".agents/skills/factory-context/SKILL.md",
                       ".agents/skills/factory-implementation/SKILL.md",
                       ".agents/skills/factory-review/SKILL.md"})
ZIP_DATE = (1980, 1, 1, 0, 0, 0)
COMPAT = {"python": ">=3.12", "profileSchema": 1, "workOrderSchema": 1,
          "evidenceSchema": 1, "installationSchema": 1}
MANIFEST_KEYS = {"schemaVersion", "kind", "publisher", "releaseId", "factoryVersion", "sourceCommit",
                 "sourceTree", "compatibility", "files"}
TRUST_KEYS = {"schemaVersion", "kind", "publisher", "releaseId", "factoryVersion", "sourceCommit",
              "sourceTree", "bundleSha256", "expiresOn", "compatibility"}
FILE_KEYS = {"path", "size", "sha256"}


class DistributionError(ValueError):
    """Malformed, unsafe or not independently trusted bundle."""


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _canonical(data: object) -> bytes:
    return (json.dumps(data, sort_keys=True, ensure_ascii=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode("utf-8")


def _pairs(pairs: list[tuple[str, object]]) -> dict:
    out: dict = {}
    for key, value in pairs:
        if key in out:
            raise DistributionError("duplicate JSON member")
        out[key] = value
    return out


def _read_json(raw: bytes, context: str) -> dict:
    if len(raw) > MAX_METADATA:
        raise DistributionError(f"{context}: oversized JSON")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs)
    except DistributionError:
        raise
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise DistributionError(f"{context}: invalid JSON") from exc
    if type(value) is not dict:
        raise DistributionError(f"{context}: expected object")
    return value


def _fields(value: Any, keys: set[str], context: str) -> dict:
    if type(value) is not dict or set(value) != keys:
        raise DistributionError(f"{context}: unsupported fields")
    return value


def _name(value: Any, context: str) -> str:
    if type(value) is not str or not NAME.fullmatch(value):
        raise DistributionError(f"{context}: invalid identity")
    return value


def _path(value: Any) -> str:
    if (type(value) is not str or not value or len(value) > 512
            or value.startswith(("/", "\\")) or "\\" in value or ":" in value
            or value != value.strip() or "\x00" in value
            or any(x in ("", ".", "..", ".git") or x.endswith((" ", "."))
                   for x in value.split("/"))):
        raise DistributionError("unsafe archive path")
    # No extracted path is ever written, but cross-platform path aliases still fail.
    if any(x.upper().split(".")[0] in {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(1, 10)],
                                          *[f"LPT{i}" for i in range(1, 10)]}
           for x in value.split("/")):
        raise DistributionError("Windows reserved archive name")
    return value


def _portable(path: str) -> bool:
    return (path in PORTABLE_EXACT or path.endswith(".py") and path.startswith("src/sf/")
            or path in {p + "SKILL.md" for p in PORTABLE_PREFIXES[1:]})


def _identity(value: Any, context: str) -> str:
    if type(value) is not str or not HEX40.fullmatch(value):
        raise DistributionError(f"{context}: full lowercase Git SHA required")
    return value


def _compat(value: Any) -> dict:
    if value != COMPAT or type(value) is not dict:
        raise DistributionError("unsupported factory schema compatibility")
    return value


def _manifest(value: Any) -> dict:
    m = _fields(value, MANIFEST_KEYS, "manifest")
    if type(m["schemaVersion"]) is not int or m["schemaVersion"] != 1 or m["kind"] != "sf-offline-bundle":
        raise DistributionError("unsupported bundle manifest")
    _name(m["publisher"], "publisher")
    _name(m["releaseId"], "releaseId")
    if type(m["factoryVersion"]) is not str or not VERSION.fullmatch(m["factoryVersion"]):
        raise DistributionError("invalid factory version")
    _identity(m["sourceCommit"], "sourceCommit")
    _identity(m["sourceTree"], "sourceTree")
    _compat(m["compatibility"])
    files = m["files"]
    if type(files) is not list or not len(MANDATORY) <= len(files) <= MAX_FILES:
        raise DistributionError("invalid file inventory")
    previous = ""
    seen_casefold: set[str] = set()
    for file in files:
        f = _fields(file, FILE_KEYS, "manifest file")
        path = _path(f["path"])
        if not _portable(path) or path <= previous or path.casefold() in seen_casefold:
            raise DistributionError("unexpected, duplicate or unordered factory file")
        previous = path
        seen_casefold.add(path.casefold())
        if type(f["size"]) is not int or not 0 <= f["size"] <= MAX_FILE:
            raise DistributionError("invalid file size")
        if type(f["sha256"]) is not str or not HEX64.fullmatch(f["sha256"]):
            raise DistributionError("invalid file digest")
    if not MANDATORY <= {f["path"] for f in files}:
        raise DistributionError("mandatory factory core missing")
    return m


def _trusted(value: Any) -> dict:
    t = _fields(value, TRUST_KEYS, "external trust record")
    if type(t["schemaVersion"]) is not int or t["schemaVersion"] != 1 or t["kind"] != "sf-out-of-band-release-pin":
        raise DistributionError("unsupported trusted release policy")
    _name(t["publisher"], "publisher")
    _name(t["releaseId"], "releaseId")
    if type(t["factoryVersion"]) is not str or not VERSION.fullmatch(t["factoryVersion"]):
        raise DistributionError("invalid trusted version")
    _identity(t["sourceCommit"], "trusted sourceCommit")
    _identity(t["sourceTree"], "trusted sourceTree")
    if type(t["bundleSha256"]) is not str or not HEX64.fullmatch(t["bundleSha256"]):
        raise DistributionError("invalid trusted digest")
    if type(t["expiresOn"]) is not str or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", t["expiresOn"]):
        raise DistributionError("invalid trust expiry")
    try:
        date.fromisoformat(t["expiresOn"])
    except ValueError as exc:
        raise DistributionError("invalid trust expiry") from exc
    _compat(t["compatibility"])
    return t


def _root(root: Path) -> Path:
    if root.is_symlink() or not root.is_dir():
        raise DistributionError("root must be a real Git worktree")
    return root.resolve(strict=True)


def _git(root: Path, *argv: str) -> bytes:
    try:
        p = subprocess.run(["git", "-C", str(root), "-c", "core.fsmonitor=false",
                            "-c", "core.untrackedCache=false", "--no-pager", *argv],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15,
                           env={**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0"}, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DistributionError("Git evidence unavailable") from exc
    if p.returncode:
        raise DistributionError("Git evidence unavailable: " + argv[0])
    return p.stdout


def _source(root: Path) -> tuple[str, str, dict[str, bytes]]:
    root = _root(root)
    if Path(os.fsdecode(_git(root, "rev-parse", "--show-toplevel").strip())).resolve() != root:
        raise DistributionError("root must be Git top-level")
    if _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all"):
        raise DistributionError("dirty source cannot be distributed")
    commit = _git(root, "rev-parse", "HEAD").decode("ascii").strip()
    tree = _git(root, "rev-parse", "HEAD^{tree}").decode("ascii").strip()
    _identity(commit, "commit")
    _identity(tree, "tree")
    blob: dict[str, bytes] = {}
    records = _git(root, "ls-files", "-s", "-z").split(b"\0")
    for entry in records:
        if not entry:
            continue
        try:
            header, raw_path = entry.split(b"\t", 1)
            mode, _, stage = header.split()
            path = os.fsdecode(raw_path)
        except (ValueError, UnicodeError) as exc:
            raise DistributionError("invalid Git index") from exc
        if not _portable(path):
            continue
        _path(path)
        if mode not in (b"100644", b"100755") or stage != b"0":
            raise DistributionError("symlink, submodule or unmerged factory file")
        content = _git(root, "show", f"HEAD:{path}")
        if len(content) > MAX_FILE:
            raise DistributionError("oversized factory file")
        if path in blob:
            raise DistributionError("duplicate tracked file")
        blob[path] = content
    if len(blob) > MAX_FILES or not MANDATORY <= blob.keys():
        raise DistributionError("missing required factory portable core")
    if len({p.casefold() for p in blob}) != len(blob):
        raise DistributionError("portable factory filename collision")
    return commit, tree, blob


def _zi(name: str) -> zipfile.ZipInfo:
    zi = zipfile.ZipInfo(name, ZIP_DATE)
    zi.create_system = 3
    zi.external_attr = (0o100644 << 16)
    zi.compress_type = zipfile.ZIP_STORED
    zi.flag_bits = 0
    return zi


def build_bytes(root: Path, *, publisher: str, release_id: str) -> bytes:
    """Build bytes, without filesystem writes. Requires clean committed source."""
    _name(publisher, "publisher")
    _name(release_id, "releaseId")
    commit, tree, files = _source(root)
    manifest = {"schemaVersion": 1, "kind": "sf-offline-bundle",
                "publisher": publisher, "releaseId": release_id, "factoryVersion": __version__,
                "sourceCommit": commit, "sourceTree": tree, "compatibility": dict(COMPAT),
                "files": [{"path": name, "size": len(raw), "sha256": _sha(raw)}
                          for name, raw in sorted(files.items())]}
    _manifest(manifest)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", allowZip64=False) as z:
        z.writestr(_zi("manifest.json"), _canonical(manifest))
        for name in sorted(files):
            z.writestr(_zi(name), files[name])
    data = out.getvalue()
    if len(data) > MAX_BUNDLE:
        raise DistributionError("bundle too large")
    return data


def _regular_bytes(path: Path, limit: int, context: str) -> bytes:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise DistributionError(f"{context}: missing, symlinked or oversized")
    return path.read_bytes()


def _exclusive(path: Path, value: bytes) -> None:
    if path.is_symlink() or path.exists() or path.parent.is_symlink() or not path.parent.is_dir():
        raise DistributionError("output must not exist; parent must be a real directory")
    # No silent overwrite; no auto-created parent; account for hardlink/symlink race with O_EXCL.
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise DistributionError("output already exists") from exc


def build_bundle(root: Path, output: Path, *, publisher: str, release_id: str) -> dict:
    # Validate destination before doing work, but no output is written until all checks complete.
    if output.is_symlink() or output.exists() or not output.parent.is_dir() or output.parent.is_symlink():
        raise DistributionError("unsafe output path")
    data = build_bytes(root, publisher=publisher, release_id=release_id)
    _exclusive(output, data)
    return {"schemaVersion": 1, "status": "built-not-authenticated", "bundleSha256": _sha(data),
            "bytes": len(data), "fileWritten": str(output), "publisherClaim": publisher,
            "releaseId": release_id, "releaseQualified": False, "accepted": False}


def verify_bytes(archive: bytes, trust: dict, *, today: date | None = None) -> dict:
    """Verify canonical ZIP against independently supplied out-of-band trust pin."""
    t = _trusted(trust)
    if date.fromisoformat(t["expiresOn"]) < (today or datetime.now(timezone.utc).date()):
        raise DistributionError("trusted release policy expired")
    if len(archive) > MAX_BUNDLE or len(archive) < 100:
        raise DistributionError("oversized or truncated archive")
    if _sha(archive) != t["bundleSha256"]:
        raise DistributionError("bundle digest does not match external trust anchor")
    try:
        with zipfile.ZipFile(io.BytesIO(archive), "r", allowZip64=False) as z:
            listing = z.infolist()
            if not len(MANDATORY) + 1 <= len(listing) <= MAX_FILES + 1:
                raise DistributionError("invalid ZIP member count")
            names = [x.filename for x in listing]
            if names[0] != "manifest.json" or names[1:] != sorted(names[1:]):
                raise DistributionError("unexpected ZIP ordering")
            if len(names) != len(set(names)) or len(names) != len({x.casefold() for x in names}):
                raise DistributionError("duplicate ZIP names")
            for entry in listing:
                if entry.filename != "manifest.json":
                    _path(entry.filename)
                if (entry.is_dir() or entry.compress_type != zipfile.ZIP_STORED
                        or entry.file_size > MAX_FILE or entry.compress_size != entry.file_size
                        or entry.create_system != 3 or entry.external_attr >> 16 != 0o100644
                        or entry.date_time != ZIP_DATE):
                    raise DistributionError("unsafe or noncanonical ZIP entry")
            raw_manifest = z.read(listing[0])
            manifest = _manifest(_read_json(raw_manifest, "bundle manifest"))
            if raw_manifest != _canonical(manifest):
                raise DistributionError("noncanonical bundle manifest")
            if names[1:] != [x["path"] for x in manifest["files"]]:
                raise DistributionError("ZIP contents disagree with manifest")
            for entry, expected in zip(listing[1:], manifest["files"]):
                raw = z.read(entry)
                if len(raw) != expected["size"] or _sha(raw) != expected["sha256"]:
                    raise DistributionError("corrupt bundle member")
    except (zipfile.BadZipFile, EOFError, OSError, ValueError, RuntimeError) as exc:
        if isinstance(exc, DistributionError):
            raise
        raise DistributionError("corrupt or unsupported bundle") from exc
    for field in ("publisher", "releaseId", "factoryVersion", "sourceCommit", "sourceTree", "compatibility"):
        if manifest[field] != t[field]:
            raise DistributionError("bundle identity or compatibility not authorized by trust pin: " + field)
    lock = {"schemaVersion": 1, "kind": "sf-pinned-bundle-lock",
            "publisher": manifest["publisher"], "releaseId": manifest["releaseId"],
            "factoryVersion": manifest["factoryVersion"], "sourceCommit": manifest["sourceCommit"],
            "sourceTree": manifest["sourceTree"], "bundleSha256": _sha(archive),
            "compatibility": manifest["compatibility"], "trustMode": "externally-provisioned-digest"}
    return {"schemaVersion": 1, "status": "matched-external-release-pin", "bundleDigestVerified": True,
            "trustMode": "externally-provisioned-digest", "publisherSignatureVerified": False,
            "independentTrustProvisioningVerified": False, "sourceAuthenticityConditional": True,
            "filesVerified": len(manifest["files"]), "lock": lock,
            "accepted": False, "releaseQualified": False, "mergeAuthorized": False}


def verify_bundle(bundle_path: Path, trust_path: Path, *, lock_out: Path | None = None) -> dict:
    if bundle_path.resolve(strict=False) == trust_path.resolve(strict=False):
        raise DistributionError("bundle and trust cannot be same file")
    if lock_out is not None and (lock_out.exists() or lock_out.is_symlink()):
        raise DistributionError("lock output already exists")
    trust = _read_json(_regular_bytes(trust_path, MAX_METADATA, "trust"), "trust")
    raw = _regular_bytes(bundle_path, MAX_BUNDLE, "bundle")
    result = verify_bytes(raw, trust)
    if lock_out is not None:
        _exclusive(lock_out, _canonical(result["lock"]))
        result["lockWritten"] = str(lock_out)
    return result
