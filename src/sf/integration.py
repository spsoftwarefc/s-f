"""SF-05: deterministic, zero-write, repository-local integration planning.

This module never applies plans, executes project code or touches Git/CI remotely.
Plan fields are proposals and TOCTOU-sensitive observations, not authorization.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .inventory import InventoryError, inventory
from .profile import ProfileError, read_profile

MAX_OBSERVED_BYTES = 1024 * 1024
SCHEMA_VERSION = 1


class IntegrationError(ValueError):
    """Unsafe or unavailable planning prerequisite."""


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _text(data: object) -> str:
    return _canonical(data) + "\n"


def _observe(root: Path, name: str) -> dict:
    """Observe only predetermined paths; never follow a symlink or read large files."""
    current = root
    segments = name.split("/")
    for i, segment in enumerate(segments):
        if not current.is_dir():
            return {"state": "blocked", "reason": "non-directory-parent"}
        try:
            matching = [p for p in current.iterdir() if p.name.casefold() == segment.casefold()]
        except OSError as exc:
            raise IntegrationError("unreadable destination directory") from exc
        if any(p.name != segment for p in matching):
            return {"state": "blocked", "reason": "case-collision"}
        current = current / segment
        if current.is_symlink():
            return {"state": "blocked", "reason": "symlink"}
        if not current.exists():
            return {"state": "absent"}
        if i < len(segments) - 1 and not current.is_dir():
            return {"state": "blocked", "reason": "non-directory-parent"}
    if not current.is_file():
        return {"state": "blocked", "reason": "not-regular-file"}
    try:
        if current.stat().st_size > MAX_OBSERVED_BYTES:
            return {"state": "blocked", "reason": "oversized-existing-file"}
        return {"state": "file", "sha256": _digest(current.read_bytes())}
    except OSError as exc:
        raise IntegrationError("cannot read destination file") from exc


def _payloads(profile: dict, *, add_route: bool) -> dict[str, str]:
    project = profile["project"]["id"]
    guide = (
        "# s-f factory project routing\n\n"
        "This folder is factory-owned guidance, not a grant of project authority.\n"
        "Preserve existing project instructions, CI and release controls.\n"
        "Start each implementation with a committed work order; verify actual evidence.\n"
        "Do not treat a local plan as permission to merge, deploy or execute commands.\n"
        "For the active project, consult the project profile and existing instructions.\n"
    )
    payloads = {
        ".s-f/PROJECT.md": "# Factory integration\n\nRead .s-f/INSTRUCTIONS.md and .s-f/profile.json.\nExisting project controls prevail; conflicts require review.\n",
        ".s-f/INSTRUCTIONS.md": guide,
        ".s-f/profile.json": _text(profile),
    }
    if add_route:
        payloads["AGENTS.md"] = (
            "# Project agent routing\n\n"
            "Consult `.s-f/INSTRUCTIONS.md` and `.s-f/PROJECT.md` for factory guidance.\n"
            "Existing project security, tests, CI and release rules remain authoritative.\n"
        )
    manifest = {"schemaVersion": 1, "owner": "s-f", "projectId": project,
                "files": [{"path": name, "sha256": _digest(body.encode("utf-8"))}
                          for name, body in sorted(payloads.items())]}
    payloads[".s-f/OWNERSHIP.json"] = _text(manifest)
    return payloads


def plan_install(root: Path, profile_path: Path) -> dict:
    """Return a deterministic, inspectable dry-run: absolutely no project writes."""
    if root.is_symlink() or not root.is_dir():
        raise IntegrationError("project root must be a real directory")
    root = root.resolve(strict=True)
    profile = read_profile(profile_path, root=root)
    report = inventory(root)  # bounded, symlink-avoiding, read-only
    instructions = _observe(root, "AGENTS.md")
    # Treat pre-existing factory files as owned only when the entire generated
    # ownership manifest matches. This permits repeat-plan no-op after SF-06
    # apply without claiming that an arbitrary .s-f directory belongs to us.
    original_route = _payloads(profile, add_route=True)
    manifest_seen = _observe(root, ".s-f/OWNERSHIP.json")
    route_owned = (
        instructions["state"] == "file"
        and instructions["sha256"] == _digest(original_route["AGENTS.md"].encode("utf-8"))
        and manifest_seen.get("sha256") == _digest(original_route[".s-f/OWNERSHIP.json"].encode("utf-8"))
    )
    add_route = instructions["state"] == "absent" or route_owned
    payloads = _payloads(profile, add_route=add_route)
    known_owned = manifest_seen.get("sha256") == _digest(payloads[".s-f/OWNERSHIP.json"].encode("utf-8"))
    factory_prefix = root / ".s-f"
    foreign_prefix = factory_prefix.is_dir() and not factory_prefix.is_symlink() and not known_owned
    prefix_reason = "existing-factory-namespace-requires-SF-06-adoption" if foreign_prefix else None
    changes: list[dict] = []
    conflicts: list[dict] = []
    for name, data in sorted(payloads.items()):
        desired = _digest(data.encode("utf-8"))
        observed = _observe(root, name)
        state = observed["state"]
        if name.startswith(".s-f/") and foreign_prefix:
            disposition = "blocked"
            reason = prefix_reason
        elif state == "absent":
            disposition = "add"
            reason = None
        elif state == "file" and observed["sha256"] == desired:
            disposition = "unchanged"
            reason = None
        else:
            disposition = "blocked"
            reason = observed.get("reason", "preexisting-content")
        item = {"path": name, "disposition": disposition,
                "expected": observed, "desiredSha256": desired, "content": data}
        changes.append(item)
        if disposition == "blocked":
            conflicts.append({"path": name, "reason": reason})
    if instructions["state"] != "absent" and not route_owned:
        conflicts.append({"path": "AGENTS.md", "reason": "existing-instructions-manual-routing"})
    # Existing custom CI never becomes a write target. Only a manual suggestion.
    ci = {"existingWorkflows": report["workflowFiles"], "writesPlanned": [],
          "proposal": "review-existing-ci" if report["workflowFiles"] else "define-ci-in-SF-10",
          "enforced": False}
    stable_inventory = {key: report[key] for key in (
        "components", "instructionFiles", "workflowFiles", "limits")}
    snapshot = _digest(_canonical(stable_inventory).encode("utf-8"))
    changes.sort(key=lambda x: x["path"])
    conflicts.sort(key=lambda x: (x["path"], x["reason"]))
    return {"schemaVersion": SCHEMA_VERSION, "operation": "integrate-dry-run",
            "projectId": profile["project"]["id"], "root": root.as_posix(),
            "baseline": {"inventorySha256": snapshot, "gitCommit": None,
                         "gitTree": None, "dirtyPaths": None, "dirtyState": "unknown"},
            "profileSha256": _digest(_canonical(profile).encode("utf-8")),
            "changes": changes, "conflicts": conflicts,
            "preserved": {"instructionFiles": report["instructionFiles"],
                          "workflowFiles": report["workflowFiles"],
                          "nativeCommands": "untouched", "projectData": "untouched"},
            "ci": ci, "installationAuthorized": False, "filesWritten": [],
            "releaseQualified": False,
            "readiness": "blocked" if conflicts else "plan-only"}
