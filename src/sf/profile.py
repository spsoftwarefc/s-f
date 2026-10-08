"""Bounded offline project profile v1 contracts.

Profile content is untrusted declarative data. Validation does not execute commands.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

MAX_PROFILE_BYTES = 1024 * 1024
MAX_COMMANDS = 100
MAX_COMPONENTS = 128
MAX_EDGES = 512
PROFILE_KEYS = frozenset({"schemaVersion", "project", "commands", "components"})
PROJECT_KEYS = frozenset({"id"})
COMMAND_KEYS = frozenset({"argv", "cwd", "risk", "timeoutSeconds", "network"})
COMPONENT_KEYS = frozenset({"id", "path", "stack", "dependsOn", "checks"})
STACKS = frozenset({"python", "node", "rust", "go", "custom"})
RISKS = frozenset({"read-only", "build", "mutating", "external"})
IDENTIFIER = re.compile(r"[a-zA-Z][a-zA-Z0-9_.-]{0,63}\Z")


class ProfileError(ValueError):
    """Malformed, unsafe or incompatible profile."""


def _identifier(value: object) -> bool:
    return type(value) is str and IDENTIFIER.fullmatch(value) is not None


def _relative(value: object, *, root_allowed: bool = False) -> bool:
    if type(value) is not str:
        return False
    if root_allowed and value == ".":
        return True
    return (
        0 < len(value) <= 1024
        and "\\" not in value
        and not value.startswith("/")
        and ":" not in value
        and "\x00" not in value
        and all(part not in ("", ".", "..") for part in value.split("/"))
    )


def _distinct_identifiers(items: list[str], label: str) -> None:
    if any(not _identifier(item) for item in items) or len({item.casefold() for item in items}) != len(items):
        raise ProfileError(f"duplicate {label} (case-insensitive)")


def _topological_components(components: list[dict]) -> list[str]:
    """Stable dependency-first order; raises on missing/cyclic dependencies."""
    ids = {c["id"] for c in components}
    graph = {c["id"]: tuple(c.get("dependsOn", [])) for c in components}
    for node, deps in graph.items():
        for dep in deps:
            if dep not in ids:
                raise ProfileError(f"unknown component dependency: {node} -> {dep}")
    visiting: set[str] = set()
    completed: set[str] = set()
    result: list[str] = []

    def visit(node: str) -> None:
        if node in completed:
            return
        if node in visiting:
            raise ProfileError(f"cyclic component dependency at {node}")
        visiting.add(node)
        for dep in sorted(graph[node]):
            visit(dep)
        visiting.remove(node)
        completed.add(node)
        result.append(node)

    for node in sorted(graph):
        visit(node)
    return result


def component_order(profile: dict) -> list[str]:
    """Return deterministic dependency-first component ordering."""
    return _topological_components(profile.get("components", []))


def validate_profile(data: object) -> dict:
    if type(data) is not dict or not {"schemaVersion", "project", "commands"} <= set(data):
        raise ProfileError("profile requires schemaVersion, project and commands")
    if not set(data) <= PROFILE_KEYS:
        raise ProfileError("unknown top-level profile fields")
    if type(data["schemaVersion"]) is not int or data["schemaVersion"] != 1:
        raise ProfileError("unsupported profile schemaVersion")

    project = data["project"]
    if type(project) is not dict or set(project) != PROJECT_KEYS or not _relative(project["id"]):
        raise ProfileError("project.id must be a safe relative identifier")

    commands = data["commands"]
    if type(commands) is not dict or len(commands) > MAX_COMMANDS:
        raise ProfileError("commands must be a bounded object")
    _distinct_identifiers(list(commands), "command identifiers")
    for name, spec in commands.items():
        if not _identifier(name) or type(spec) is not dict:
            raise ProfileError("invalid command name or specification")
        if not {"argv", "cwd"} <= set(spec) or not set(spec) <= COMMAND_KEYS:
            raise ProfileError(f"invalid command fields: {name}")
        argv, cwd = spec["argv"], spec["cwd"]
        if (
            type(argv) is not list or not 1 <= len(argv) <= 128
            or any(type(arg) is not str or not arg or len(arg) > 4096 or "\x00" in arg for arg in argv)
        ):
            raise ProfileError("argv must be a bounded array of nonempty strings")
        if not _relative(cwd, root_allowed=True):
            raise ProfileError("cwd must be a safe project-relative directory")
        if "risk" in spec and (type(spec["risk"]) is not str or spec["risk"] not in RISKS):
            raise ProfileError("invalid command risk")
        if "network" in spec and type(spec["network"]) is not bool:
            raise ProfileError("network must be boolean")
        if "timeoutSeconds" in spec and (
            type(spec["timeoutSeconds"]) is not int or not 1 <= spec["timeoutSeconds"] <= 3600
        ):
            raise ProfileError("invalid command timeoutSeconds")

    components = data.get("components", [])
    if type(components) is not list or len(components) > MAX_COMPONENTS:
        raise ProfileError("components must be a bounded array")
    names: list[str] = []
    edge_count = 0
    for component in components:
        if type(component) is not dict or not {"id", "path", "stack"} <= set(component):
            raise ProfileError("component requires id, path and stack")
        if not set(component) <= COMPONENT_KEYS:
            raise ProfileError("unknown component fields")
        name = component["id"]
        if not _identifier(name) or not _relative(component["path"], root_allowed=True):
            raise ProfileError("invalid component id or path")
        if type(component["stack"]) is not str or component["stack"] not in STACKS:
            raise ProfileError("unsupported component stack; use custom for unknown tools")
        depends = component.get("dependsOn", [])
        checks = component.get("checks", [])
        if type(depends) is not list or any(not _identifier(x) for x in depends):
            raise ProfileError("dependsOn must be a list of component ids")
        if type(checks) is not list or any(not _identifier(x) or x not in commands for x in checks):
            raise ProfileError("checks must reference declared command ids")
        if len(set(depends)) != len(depends) or len(set(checks)) != len(checks):
            raise ProfileError("duplicate component dependencies or checks")
        edge_count += len(depends)
        names.append(name)
    if edge_count > MAX_EDGES:
        raise ProfileError("too many component dependencies")
    _distinct_identifiers(names, "component identifiers")
    _topological_components(components)
    return data


def validate_project_paths(profile: dict, root: Path) -> None:
    """Check declared directories in an existing root without following symlinks."""
    if root.is_symlink() or not root.is_dir():
        raise ProfileError("project root must be a directory, not a symlink")
    root = root.resolve(strict=True)
    directories = [spec["cwd"] for spec in profile["commands"].values()]
    directories.extend(c["path"] for c in profile.get("components", []))
    for directory in directories:
        current = root
        for part in ([] if directory == "." else directory.split("/")):
            current = current / part
            if current.is_symlink():
                raise ProfileError(f"project directory crosses symlink: {directory}")
        if not current.is_dir():
            raise ProfileError(f"project directory missing or not a directory: {directory}")
        if not current.resolve(strict=True).is_relative_to(root):
            raise ProfileError(f"project directory escapes root: {directory}")


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict:
    value: dict = {}
    for key, item in pairs:
        if key in value:
            raise ProfileError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def read_profile(path: Path, *, root: Path | None = None) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ProfileError("profile path is missing or a symlink")
    if path.stat().st_size > MAX_PROFILE_BYTES:
        raise ProfileError("profile too large")
    try:
        data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_pairs)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ProfileError("invalid UTF-8 or JSON") from exc
    profile = validate_profile(data)
    if root is not None:
        validate_project_paths(profile, root)
    return profile
