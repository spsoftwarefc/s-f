"""SF-13I: byte-exact pinned portable installer using SF-06 checked effects.

This module enforces only externally pinned bundle identity, not independently
authenticated trust-file issuance, publisher signing or release qualification.
Legacy SF-06 plans remain separately marked as unqualified development previews.
"""
from __future__ import annotations

import base64
import io
import json
import zipfile
from pathlib import Path

from .distribution import (
    MAX_BUNDLE, MAX_FILES, MAX_METADATA, MANDATORY, _canonical as canonical_bytes,
    _path as portable_path, _portable, _read_json as distribution_json,
    _regular_bytes, verify_bytes,
)
from .integration import (
    IntegrationError, _digest, _observe, _payloads, _text, plan_install,
)
from .profile import read_profile, validate_profile
from . import lifecycle as fs

RECORD = ".s-f/FACTORY_LOCK.json"
PORTABLE = ".s-f/portable/"
OWNERSHIP = ".s-f/OWNERSHIP.json"
PINNED_SCHEMA = 2
MAX_PINNED_JOURNAL = 42 * 1024 * 1024
MAX_PINNED_PLAN = 10 * 1024 * 1024
HEX = set("0123456789abcdef")


def _strict_file(path: Path, limit: int) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise IntegrationError("missing, unsafe or oversized pinned installation metadata")
    raw = path.read_bytes()
    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=fs._pairs)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise IntegrationError("invalid pinned installation JSON") from exc
    if type(data) is not dict or raw != (_text(data)).encode("utf-8"):
        raise IntegrationError("noncanonical pinned installation metadata")
    return data


def _verified_source(bundle: Path | None, trust: Path | None,
                     lock: Path | None) -> tuple[dict, dict[str, bytes]]:
    if not all(x is not None for x in (bundle, trust, lock)):
        raise IntegrationError("qualified install/upgrade/recovery requires --bundle, --trust and --lock")
    for a, b in ((bundle, trust), (bundle, lock), (trust, lock)):
        if a.resolve(strict=False) == b.resolve(strict=False):
            raise IntegrationError("distribution proof inputs must be distinct")
    archive = _regular_bytes(bundle, MAX_BUNDLE, "bundle")
    trust_data = distribution_json(_regular_bytes(trust, MAX_METADATA, "trust"), "trust")
    lock_raw = _regular_bytes(lock, MAX_METADATA, "installation lock")
    locked = distribution_json(lock_raw, "installation lock")
    if lock_raw != canonical_bytes(locked):
        raise IntegrationError("noncanonical installation lock")
    checked = verify_bytes(archive, trust_data)
    if locked != checked["lock"]:
        raise IntegrationError("installation lock mismatches independently verified archive")
    with zipfile.ZipFile(io.BytesIO(archive)) as zipf:
        manifest = json.loads(zipf.read("manifest.json"))
        # verify_bytes already validated every member, exact paths, order and sha256.
        members = {f["path"]: zipf.read(f["path"]) for f in manifest["files"]}
    if set(members) != {f["path"] for f in manifest["files"]}:
        raise IntegrationError("distribution inventory disagreement")
    return locked, members


def _record(lock: dict, members: dict[str, bytes]) -> dict:
    return {
        "schemaVersion": 1, "kind": "sf-pinned-installed-portable",
        "lock": lock,
        "files": [
            {"path": path, "size": len(raw), "sha256": _digest(raw)}
            for path, raw in sorted(members.items())
        ],
    }


def _allowed_member_records(files: object) -> None:
    if type(files) is not list or not len(MANDATORY) <= len(files) <= MAX_FILES:
        raise IntegrationError("invalid installed portable inventory")
    last = ""
    folded = set()
    for item in files:
        if type(item) is not dict or set(item) != {"path", "size", "sha256"}:
            raise IntegrationError("malformed installed file inventory")
        name = portable_path(item["path"])
        if not _portable(name) or name <= last or name.casefold() in folded:
            raise IntegrationError("malformed or duplicate installed portable path")
        if type(item["size"]) is not int or not 0 <= item["size"] <= 2 * 1024 * 1024:
            raise IntegrationError("invalid installed file length")
        if (type(item["sha256"]) is not str or len(item["sha256"]) != 64
                or set(item["sha256"]) - HEX):
            raise IntegrationError("invalid installed member digest")
        last = name
        folded.add(name.casefold())
    if not MANDATORY <= {x["path"] for x in files}:
        raise IntegrationError("missing mandatory installed portable members")


def _new_files(profile: dict, route: bool, lock: dict,
               members: dict[str, bytes]) -> dict[str, bytes]:
    files = {name: body.encode("utf-8")
             for name, body in _payloads(profile, add_route=route).items()
             if name != OWNERSHIP}
    record = _record(lock, members)
    files[RECORD] = canonical_bytes(record)
    for path, raw in members.items():
        files[PORTABLE + path] = raw
    manifest = {
        "schemaVersion": 1, "owner": "s-f",
        "projectId": profile["project"]["id"],
        "files": [{"path": name, "sha256": _digest(raw)}
                  for name, raw in sorted(files.items())],
    }
    files[OWNERSHIP] = _text(manifest).encode("utf-8")
    return files


def _old_inventory(profile: dict, route: bool, record: dict) -> dict[str, str]:
    if set(record) != {"schemaVersion", "kind", "lock", "files"} or (
            type(record["schemaVersion"]) is not int or record["schemaVersion"] != 1
            or record["kind"] != "sf-pinned-installed-portable"):
        raise IntegrationError("unrecognized installed pinned distribution record")
    _allowed_member_records(record["files"])
    generated = {
        name: _digest(body.encode("utf-8"))
        for name, body in _payloads(profile, add_route=route).items()
        if name != OWNERSHIP
    }
    generated[RECORD] = _digest(canonical_bytes(record))
    for member in record["files"]:
        generated[PORTABLE + member["path"]] = member["sha256"]
    ownership = {
        "schemaVersion": 1, "owner": "s-f", "projectId": profile["project"]["id"],
        "files": [{"path": k, "sha256": v} for k, v in sorted(generated.items())],
    }
    generated[OWNERSHIP] = _digest(_text(ownership).encode("utf-8"))
    return generated


def _installed(root: Path) -> tuple[dict, bool, dict[str, str], dict]:
    """Validate installed owned-path inventory before using it for upgrade/removal."""
    record = _strict_file(root / RECORD, MAX_METADATA)
    profile = read_profile(root / ".s-f/profile.json", root=root)
    ownership = _strict_file(root / OWNERSHIP, MAX_METADATA)
    if (set(ownership) != {"schemaVersion", "owner", "projectId", "files"}
            or type(ownership["schemaVersion"]) is not int
            or ownership["schemaVersion"] != 1 or ownership["owner"] != "s-f"
            or ownership["projectId"] != profile["project"]["id"]):
        raise IntegrationError("invalid pinned ownership")
    rows = ownership["files"]
    if type(rows) is not list or not rows:
        raise IntegrationError("invalid pinned owner paths")
    route = any(x == {"path": "AGENTS.md", "sha256": _digest(
        _payloads(profile, add_route=True)["AGENTS.md"].encode("utf-8"))}
        for x in rows)
    old_hashes = _old_inventory(profile, route, record)
    if ownership["files"] != [
            {"path": k, "sha256": v}
            for k, v in sorted(old_hashes.items()) if k != OWNERSHIP]:
        raise IntegrationError("ownership does not match verified managed path inventory")
    return profile, route, old_hashes, record


def _steps(old: dict[str, str], desired: dict[str, bytes]) -> list[dict]:
    out = []
    for name in sorted(set(old) | set(desired),
                       key=lambda x: (x == OWNERSHIP, x)):
        before = {"state": "file", "sha256": old[name]} if name in old else {"state": "absent"}
        if name in desired:
            raw = desired[name]
            after = {"state": "file", "sha256": _digest(raw),
                     "contentB64": base64.b64encode(raw).decode("ascii")}
        else:
            after = {"state": "absent"}
        out.append({"path": name, "before": before, "after": after})
    return out


def _summarize(mode: str, root: Path, source: dict | None,
               actions: list[dict], conflicts: list[dict], old: dict | None,
               new: dict | None, route: bool, ack_manual: bool) -> dict:
    conflicts.sort(key=lambda x: (x["path"], x["reason"]))
    return {
        "schemaVersion": PINNED_SCHEMA, "mode": mode, "root": root.as_posix(),
        "oldProfile": old, "newProfile": new, "routeOwned": route,
        "acknowledgedManualRoute": ack_manual, "verifiedLock": source,
        "changes": actions, "conflicts": conflicts, "ready": not conflicts,
        "installationAuthorized": False, "installedDistributionBytesVerified": False,
        "releaseQualified": False,
    }


def _prepare(mode: str, root: Path, profile_path: Path | None,
             *, bundle: Path | None, trust: Path | None, lock: Path | None,
             ack_manual: bool = False) -> tuple[dict, list[dict], dict[str, str], dict | None]:
    root = fs._root(root)
    if mode not in ("integrate", "upgrade", "remove"):
        raise IntegrationError("invalid pinned operation")
    if _observe(root, fs.JOURNAL)["state"] != "absent":
        raise IntegrationError("incomplete transaction: recover before another operation")
    if mode == "remove":
        if any(x is not None for x in (bundle, trust, lock)) or profile_path is not None:
            raise IntegrationError("remove cannot accept a new distribution/profile")
        source, members = None, {}
    else:
        source, members = _verified_source(bundle, trust, lock)
    old_profile = None
    old_record = None
    old_hashes: dict[str, str] = {}
    route = False
    conflicts: list[dict] = []
    if mode in ("upgrade", "remove"):
        old_profile, route, old_hashes, old_record = _installed(root)
    elif _observe(root, ".s-f")["state"] != "absent":
        raise IntegrationError("factory namespace already exists; use qualified upgrade")
    if mode == "integrate":
        if profile_path is None:
            raise IntegrationError("profile required for qualified install")
        sf05 = plan_install(root, profile_path)
        conflicts = list(sf05["conflicts"])
        if ack_manual:
            conflicts = [x for x in conflicts if x["reason"] != "existing-instructions-manual-routing"]
        route = any(x["path"] == "AGENTS.md" for x in sf05["changes"])
        new_profile = read_profile(profile_path, root=root)
    elif mode == "upgrade":
        if profile_path is None:
            raise IntegrationError("profile required for qualified upgrade")
        new_profile = read_profile(profile_path, root=root)
    else:
        new_profile = None
    desired = _new_files(new_profile, route, source, members) if new_profile else {}
    steps = _steps(old_hashes, desired)
    actions = []
    for step in steps:
        observed = _observe(root, step["path"])
        if fs._matches(observed, step["after"]):
            disposition = "unchanged"
        elif fs._matches(observed, step["before"]):
            disposition = "write" if step["after"]["state"] == "file" else "delete"
        else:
            disposition = "blocked"
            conflicts.append({"path": step["path"], "reason": observed.get("reason", "changed-from-owned-base")})
        actions.append({"path": step["path"], "disposition": disposition,
                        "observed": observed, "before": step["before"],
                        "after": {k: v for k, v in step["after"].items() if k != "contentB64"}})
    result = _summarize(mode, root, source, actions, conflicts, old_profile,
                        new_profile, route, ack_manual)
    return result, steps, old_hashes, old_record


def plan(mode: str, root: Path, profile: Path | None = None, *,
         bundle: Path | None = None, trust: Path | None = None,
         lock: Path | None = None, ack_manual: bool = False) -> dict:
    return _prepare(mode, root, profile, bundle=bundle, trust=trust, lock=lock,
                    ack_manual=ack_manual)[0]


def apply(root: Path, profile: Path | None, document: Path, *,
          mode: str, bundle: Path | None = None, trust: Path | None = None,
          lock: Path | None = None, ack_manual: bool = False) -> dict:
    root = fs._root(root)
    requested = fs._read_json(document, MAX_PINNED_PLAN)
    proposed, steps, old, old_record = _prepare(mode, root, profile, bundle=bundle,
                                    trust=trust, lock=lock, ack_manual=ack_manual)
    if requested != proposed:
        raise IntegrationError("stale or altered qualified lifecycle plan")
    if proposed["conflicts"]:
        raise IntegrationError("qualified lifecycle plan has unresolved conflicts")
    pending = [step for step in steps if not fs._matches(
        _observe(root, step["path"]), step["after"])]
    if not pending:
        return {"mode": mode, "status": "no-op", "changed": [],
                "installedDistributionBytesVerified": mode != "remove",
                "releaseQualified": False}
    journal = {"schemaVersion": PINNED_SCHEMA, "root": root.as_posix(),
               "mode": mode, "oldProfile": proposed["oldProfile"],
               "newProfile": proposed["newProfile"],
               "routeOwned": proposed["routeOwned"],
               "verifiedLock": proposed["verifiedLock"], "oldHashes": old,
               "oldRecord": old_record, "steps": steps}
    # Size check precedes all target writes; journal exclusivity protects against
    # competing qualified install/upgrade operations that share the same root.
    if len(_text(journal).encode("utf-8")) > MAX_PINNED_JOURNAL:
        raise IntegrationError("qualified lifecycle journal exceeds limit")
    fs._make_journal(root, journal, size_limit=MAX_PINNED_JOURNAL)
    return _resume(root, journal, bundle=bundle, trust=trust, lock=lock)


def _validate_journal(root: Path, journal: dict, *, bundle: Path | None,
                      trust: Path | None, lock: Path | None) -> None:
    keys = {"schemaVersion", "root", "mode", "oldProfile", "newProfile",
            "routeOwned", "verifiedLock", "oldHashes", "oldRecord", "steps"}
    if set(journal) != keys or type(journal["schemaVersion"]) is not int or (
            journal["schemaVersion"] != PINNED_SCHEMA or journal["root"] != root.as_posix()):
        raise IntegrationError("invalid qualified transaction identity")
    mode = journal["mode"]
    if mode not in ("integrate", "upgrade", "remove") or type(journal["routeOwned"]) is not bool:
        raise IntegrationError("invalid qualified transaction mode")
    if mode == "remove":
        if any(x is not None for x in (bundle, trust, lock)) or journal["verifiedLock"] is not None:
            raise IntegrationError("remove cannot have qualified source")
        source, members = None, {}
    else:
        source, members = _verified_source(bundle, trust, lock)
        if journal["verifiedLock"] != source:
            raise IntegrationError("stale or replaced qualified distribution proof")
    old_profile, new_profile = journal["oldProfile"], journal["newProfile"]
    if mode == "integrate" and old_profile is not None:
        raise IntegrationError("invalid install old profile")
    if mode in ("upgrade", "remove") and old_profile is None:
        raise IntegrationError("missing old qualified profile")
    if mode == "remove" and new_profile is not None:
        raise IntegrationError("removal journal cannot install new state")
    for profile in (old_profile, new_profile):
        if profile is not None:
            validate_profile(profile)
    old = journal["oldHashes"]
    if type(old) is not dict or any(type(k) is not str or type(v) is not str
                                    for k, v in old.items()):
        raise IntegrationError("invalid qualified old ownership map")
    if mode == "integrate":
        if old or journal["oldRecord"] is not None:
            raise IntegrationError("new installation claims existing ownership")
    else:
        if old != _old_inventory(old_profile, journal["routeOwned"], journal["oldRecord"]):
            raise IntegrationError("qualified journal ownership snapshot is invalid")
        current_ownership = _observe(root, OWNERSHIP)
        if current_ownership["state"] == "file":
            desired_owner = _new_files(new_profile, journal["routeOwned"], source, members).get(OWNERSHIP) if new_profile else None
            after_digest = _digest(desired_owner) if desired_owner is not None else None
            if current_ownership["sha256"] == after_digest:
                for step in journal["steps"][:-1]:
                    if not fs._matches(_observe(root, step["path"]), step["after"]):
                        raise IntegrationError("new ownership appears before all prior effects")
            elif current_ownership["sha256"] != old[OWNERSHIP]:
                raise IntegrationError("recovery old ownership changed")
        else:
            # Ownership is finalized last; the missing old manifest is safe
            # only if all preceding steps already match their desired bytes.
            for step in journal["steps"][:-1]:
                if not fs._matches(_observe(root, step["path"]), step["after"]):
                    raise IntegrationError("missing ownership with incomplete effects")
    desired = _new_files(new_profile, journal["routeOwned"], source, members) if new_profile else {}
    if journal["steps"] != _steps(old, desired):
        raise IntegrationError("qualified journal differs from verified archive and owned paths")
    if not journal["steps"] or journal["steps"][-1]["path"] != OWNERSHIP:
        raise IntegrationError("invalid qualified ownership finalization order")


def _resume(root: Path, journal: dict, *, bundle: Path | None,
            trust: Path | None, lock: Path | None) -> dict:
    _validate_journal(root, journal, bundle=bundle, trust=trust, lock=lock)
    for step in journal["steps"]:
        current = _observe(root, step["path"])
        if not fs._matches(current, step["before"]) and not fs._matches(current, step["after"]):
            raise IntegrationError("qualified recovery conflict at " + step["path"])
    changed = []
    for step in journal["steps"]:
        if fs._checked_effect(root, step):
            changed.append(step["path"])
    for step in journal["steps"]:
        if not fs._matches(_observe(root, step["path"]), step["after"]):
            raise IntegrationError("installed portable member changed during final verification")
    if journal["mode"] == "remove":
        # Remove only known-now-empty portable directories, deepest first.
        parents = set()
        for step in journal["steps"]:
            name = step["path"]
            if name.startswith(PORTABLE):
                path = (root / name).parent
                while path != root and path != root / ".s-f":
                    parents.add(path)
                    path = path.parent
        for path in sorted(parents, key=lambda p: len(p.parts), reverse=True):
            if path.is_dir() and not path.is_symlink():
                try:
                    path.rmdir()
                except OSError:
                    pass  # Preserve any foreign user data.
    fs._finish(root, journal["mode"])
    return {"mode": journal["mode"], "status": "completed", "changed": changed,
            "installedDistributionBytesVerified": journal["mode"] != "remove",
            "distributionVerified": journal["mode"] != "remove",
            "releaseQualified": False}


def recover(root: Path, *, bundle: Path | None = None, trust: Path | None = None,
            lock: Path | None = None) -> dict:
    root = fs._root(root)
    journal = fs._read_json(root / fs.JOURNAL, MAX_PINNED_JOURNAL)
    return _resume(root, journal, bundle=bundle, trust=trust, lock=lock)
