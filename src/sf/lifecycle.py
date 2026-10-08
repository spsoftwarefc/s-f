"""SF-06 filesystem lifecycle: opt-in, byte-checked effects with roll-forward journal.

Developer-operated tooling, not an OS sandbox or authenticated distribution channel.
Never executes profile commands, modifies project CI, or writes outside managed paths.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .distribution import DistributionError, verify_installation_lock
from .integration import IntegrationError, _canonical, _digest, _observe, _payloads, plan_install
from .profile import read_profile, validate_profile

JOURNAL = ".s-f-transaction.json"
MAX_JOURNAL_BYTES = 4 * 1024 * 1024
MAX_PLAN_BYTES = 4 * 1024 * 1024


def _read_json(path: Path, limit: int) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise IntegrationError("missing, symlinked or oversized transaction input")
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_pairs)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise IntegrationError("invalid transaction JSON") from exc
    if type(value) is not dict:
        raise IntegrationError("transaction input must be an object")
    return value


def _pairs(pairs: list[tuple[str, object]]) -> dict:
    value = {}
    for name, item in pairs:
        if name in value:
            raise ValueError("duplicate JSON member")
        value[name] = item
    return value


def _root(root: Path) -> Path:
    if root.is_symlink() or not root.is_dir():
        raise IntegrationError("root must be a real directory")
    return root.resolve(strict=True)


def _installed(root: Path) -> tuple[dict, bool, dict[str, str]]:
    if _observe(root, ".s-f/profile.json")["state"] != "file" or _observe(root, ".s-f/OWNERSHIP.json")["state"] != "file":
        raise IntegrationError("recognized factory installation is required")
    old = read_profile(root / ".s-f/profile.json")
    seen = (root / ".s-f/OWNERSHIP.json").read_bytes()
    candidates = [(flag, _payloads(old, add_route=flag)) for flag in (False, True)]
    for flag, payloads in candidates:
        if seen == payloads[".s-f/OWNERSHIP.json"].encode("utf-8"):
            return old, flag, payloads
    raise IntegrationError("ownership manifest disagrees with installed factory profile")


def _managed_steps(mode: str, old: dict | None, new: dict | None, route: bool) -> list[dict]:
    old_files = {} if old is None else _payloads(old, add_route=route)
    new_files = {} if new is None else _payloads(new, add_route=route)
    steps = []
    for name in sorted(set(old_files) | set(new_files), key=lambda x: (x == ".s-f/OWNERSHIP.json", x)):
        before = {"state": "absent"} if name not in old_files else {
            "state": "file", "sha256": _digest(old_files[name].encode("utf-8"))}
        after = {"state": "absent"} if name not in new_files else {
            "state": "file", "sha256": _digest(new_files[name].encode("utf-8")), "content": new_files[name]}
        steps.append({"path": name, "before": before, "after": after})
    return steps


def _matches(observed: dict, expected: dict) -> bool:
    return observed == {key: value for key, value in expected.items() if key != "content"}


def _distribution_binding(mode: str, bundle: Path | None, trust: Path | None,
                          lock: Path | None) -> dict | None:
    inputs = (bundle, trust, lock)
    if mode == "remove":
        if any(value is not None for value in inputs):
            raise IntegrationError("remove has no new distribution source")
        return None
    if not any(value is not None for value in inputs):
        return None  # legacy preview mode; never a provenance qualification
    if not all(value is not None for value in inputs):
        raise IntegrationError("bundle, trust and lock must all be supplied together")
    proof = verify_installation_lock(bundle, trust, lock)
    return proof["lock"]


def _plan(mode: str, root: Path, new_profile: Path | None = None, *, ack_manual: bool = False,
          bundle: Path | None = None, trust: Path | None = None,
          lock: Path | None = None) -> dict:
    root = _root(root)
    distribution = _distribution_binding(mode, bundle, trust, lock)
    if _observe(root, JOURNAL)["state"] != "absent":
        raise IntegrationError("pending transaction; run sf recover before another operation")
    if mode == "integrate":
        if new_profile is None:
            raise IntegrationError("profile required for integration")
        sf05 = plan_install(root, new_profile)
        conflicts = list(sf05["conflicts"])
        if ack_manual:
            conflicts = [x for x in conflicts if x["reason"] != "existing-instructions-manual-routing"]
        route = any(x["path"] == "AGENTS.md" for x in sf05["changes"])
        old, new = None, read_profile(new_profile, root=root)
        steps = _managed_steps(mode, old, new, route)
    elif mode in ("upgrade", "remove"):
        # Repeated removal is an explicit no-op if no factory namespace exists.
        # Do not adopt or touch an unrecognized namespace.
        if mode == "remove" and _observe(root, ".s-f")["state"] == "absent":
            old, route = None, False
        else:
            old, route, _ = _installed(root)
        if mode == "upgrade":
            if new_profile is None:
                raise IntegrationError("profile required for upgrade")
            new = read_profile(new_profile, root=root)
        else:
            if new_profile is not None:
                raise IntegrationError("remove must not take a new profile")
            new = None
        steps = _managed_steps(mode, old, new, route)
        conflicts = []
    else:
        raise IntegrationError("unknown lifecycle mode")
    actions = []
    for step in steps:
        observed = _observe(root, step["path"])
        if _matches(observed, step["after"]):
            disposition = "unchanged"
        elif _matches(observed, step["before"]):
            disposition = "write" if step["after"]["state"] == "file" else "delete"
        else:
            disposition = "blocked"
            conflicts.append({"path": step["path"], "reason": observed.get("reason", "changed-from-owned-base")})
        actions.append({"path": step["path"], "disposition": disposition,
                        "observed": observed, "before": step["before"], "after": step["after"]})
    conflicts.sort(key=lambda c: (c["path"], c["reason"]))
    result = {"schemaVersion": 1, "mode": mode, "root": root.as_posix(), "oldProfile": old,
              "newProfile": new, "routeOwned": route, "acknowledgedManualRoute": ack_manual,
              "distribution": distribution, "distributionVerified": distribution is not None,
              "installedDistributionBytesVerified": False,
              "changes": actions, "conflicts": conflicts, "ready": not conflicts,
              "installationAuthorized": False, "releaseQualified": False}
    return result


def plan_lifecycle(mode: str, root: Path, profile: Path | None = None, *, ack_manual: bool = False,
                   bundle: Path | None = None, trust: Path | None = None,
                   lock: Path | None = None) -> dict:
    """Read-only plan suitable for human inspection and later explicit --plan apply."""
    return _plan(mode, root, profile, ack_manual=ack_manual,
                 bundle=bundle, trust=trust, lock=lock)


def _fsync_dir(path: Path) -> None:
    if os.name == "posix":
        fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def _make_journal(root: Path, data: dict) -> None:
    content = (_canonical(data) + "\n").encode("utf-8")
    if len(content) > MAX_JOURNAL_BYTES:
        raise IntegrationError("journal exceeds size limit")
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(root / JOURNAL, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(content)
            out.flush()
            os.fsync(out.fileno())
        _fsync_dir(root)
    except BaseException:
        # An incomplete journal blocks future operations. No target has yet changed.
        raise


def _atomic_put(path: Path, content: str) -> None:
    parent = path.parent
    fd, tmp = tempfile.mkstemp(prefix=".sf06-write-", dir=parent)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(content.encode("utf-8"))
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, path)
        _fsync_dir(parent)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _ensure_parent(root: Path, name: str) -> None:
    parts = name.split("/")[:-1]
    current = root
    for part in parts:
        parent_view = _observe(root, current.relative_to(root).as_posix() + "/" + part) if current != root else _observe(root, part)
        if parent_view["state"] == "absent":
            (current / part).mkdir()
            _fsync_dir(current)
        elif parent_view != {"state": "blocked", "reason": "not-regular-file"}:
            raise IntegrationError("unsafe target parent")
        elif not (current / part).is_dir() or (current / part).is_symlink():
            raise IntegrationError("unsafe target parent")
        current = current / part


def _checked_effect(root: Path, step: dict) -> bool:
    name = step["path"]
    actual = _observe(root, name)
    if _matches(actual, step["after"]):
        return False
    if not _matches(actual, step["before"]):
        raise IntegrationError(f"external change or malformed transaction at {name}")
    if step["after"]["state"] == "file":
        _ensure_parent(root, name)
        _atomic_put(root / name, step["after"]["content"])
    else:
        (root / name).unlink()
        _fsync_dir((root / name).parent)
    return True


def _finish(root: Path, mode: str) -> None:
    # Remove only an empty factory directory; never touch foreign files.
    if mode == "remove":
        directory = root / ".s-f"
        if directory.is_dir() and not directory.is_symlink():
            try:
                directory.rmdir()
                _fsync_dir(root)
            except OSError:
                pass  # unrelated project data remains intact
    (root / JOURNAL).unlink()
    _fsync_dir(root)


def execute_plan(root: Path, profile: Path | None, document: Path,
                 *, mode: str, ack_manual: bool = False,
                 bundle: Path | None = None, trust: Path | None = None,
                 lock: Path | None = None) -> dict:
    """Explicit developer-authorized apply of a freshly recomputed exact plan."""
    root = _root(root)
    requested = _read_json(document, MAX_PLAN_BYTES)
    expected = _plan(mode, root, profile, ack_manual=ack_manual,
                     bundle=bundle, trust=trust, lock=lock)
    if requested != expected:
        raise IntegrationError("stale or altered plan; generate a fresh dry-run")
    if expected["conflicts"]:
        raise IntegrationError("plan has unresolved conflicts; no mutation performed")
    steps = _managed_steps(mode, expected["oldProfile"], expected["newProfile"], expected["routeOwned"])
    pending = [step for step in steps if not _matches(_observe(root, step["path"]), step["after"])]
    if not pending:
        return {"mode": mode, "status": "no-op", "changed": [],
                "distributionVerified": expected["distributionVerified"], "releaseQualified": False}
    journal = {"schemaVersion": 1, "root": root.as_posix(), "mode": mode,
               "oldProfile": expected["oldProfile"], "newProfile": expected["newProfile"],
               "routeOwned": expected["routeOwned"], "distribution": expected["distribution"],
               "steps": steps}
    _make_journal(root, journal)
    return _resume(root, journal, verified=expected["distribution"])


def _validate_journal(root: Path, journal: dict, *, verified: dict | None = None) -> None:
    if set(journal) != {"schemaVersion", "root", "mode", "oldProfile", "newProfile",
                        "routeOwned", "distribution", "steps"}:
        raise IntegrationError("invalid journal fields")
    if type(journal["schemaVersion"]) is not int or journal["schemaVersion"] != 1 or journal["root"] != root.as_posix():
        raise IntegrationError("invalid journal identity")
    mode, old, new, route = (journal[x] for x in ("mode", "oldProfile", "newProfile", "routeOwned"))
    if mode not in ("integrate", "upgrade", "remove") or type(route) is not bool:
        raise IntegrationError("invalid journal mode or route")
    if journal["distribution"] != verified:
        raise IntegrationError("recovery/install distribution identity does not match verified lock")
    if mode == "remove" and verified is not None:
        raise IntegrationError("removal must not bind new distribution")
    if mode == "integrate" and (old is not None or new is None):
        raise IntegrationError("invalid integration journal")
    if mode == "upgrade" and (old is None or new is None):
        raise IntegrationError("invalid upgrade journal")
    if mode == "remove" and (old is None or new is not None):
        raise IntegrationError("invalid removal journal")
    for profile in (old, new):
        if profile is not None:
            validate_profile(profile)
    if journal["steps"] != _managed_steps(mode, old, new, route):
        raise IntegrationError("journal differs from factory-generated managed effects")


def _resume(root: Path, journal: dict, *, verified: dict | None = None) -> dict:
    _validate_journal(root, journal, verified=verified)
    # Validate ALL steps before any new effect. This catches foreign changes or
    # tampered intermediate files without partially proceeding on recovery.
    for step in journal["steps"]:
        observed = _observe(root, step["path"])
        if not _matches(observed, step["before"]) and not _matches(observed, step["after"]):
            raise IntegrationError(f"recovery conflict at {step['path']}")
    changed = []
    for step in journal["steps"]:
        if _checked_effect(root, step):
            changed.append(step["path"])
    _finish(root, journal["mode"])
    return {"mode": journal["mode"], "status": "completed", "changed": changed,
            "distributionVerified": verified is not None, "releaseQualified": False}


def recover(root: Path, *, bundle: Path | None = None, trust: Path | None = None,
            lock: Path | None = None) -> dict:
    root = _root(root)
    observed = _observe(root, JOURNAL)
    if observed["state"] == "absent":
        return {"status": "no-op", "changed": [], "releaseQualified": False}
    if observed["state"] != "file":
        raise IntegrationError("unsafe journal path")
    journal = _read_json(root / JOURNAL, MAX_JOURNAL_BYTES)
    verified = _distribution_binding(journal.get("mode"), bundle, trust, lock)
    return _resume(root, journal, verified=verified)
