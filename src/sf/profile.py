"""Strict, bounded profile v1 bootstrap validation.

Full JSON Schema Draft 2020-12 validator follows in the versioned contracts package.
"""
from __future__ import annotations
import json
from pathlib import Path, PurePosixPath

MAX_PROFILE_BYTES = 1024 * 1024
PROFILE_KEYS = frozenset({"schemaVersion", "project", "commands"})
PROJECT_KEYS = frozenset({"id"})
COMMAND_KEYS = frozenset({"argv", "cwd"})


class ProfileError(ValueError):
    pass


def _relative(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and "\\" not in value
        and not value.startswith("/")
        and ":" not in value
        and all(part not in ("", ".", "..") for part in PurePosixPath(value).parts)
    )


def validate_profile(data: object) -> dict:
    if not isinstance(data, dict) or set(data) != PROFILE_KEYS:
        raise ProfileError("profile requires exactly schemaVersion, project, commands")
    if data["schemaVersion"] != 1 or type(data["schemaVersion"]) is not int:
        raise ProfileError("unsupported profile schemaVersion")
    project = data["project"]
    if not isinstance(project, dict) or set(project) != PROJECT_KEYS or not _relative(project["id"]):
        raise ProfileError("project.id must be a safe relative identifier")
    commands = data["commands"]
    if not isinstance(commands, dict) or len(commands) > 100:
        raise ProfileError("commands must be a bounded object")
    for name, spec in commands.items():
        if not _relative(name) or not isinstance(spec, dict) or set(spec) != COMMAND_KEYS:
            raise ProfileError("invalid command name or fields")
        argv, cwd = spec["argv"], spec["cwd"]
        if not isinstance(argv, list) or not 1 <= len(argv) <= 128 or any(
            not isinstance(arg, str) or not arg or len(arg) > 4096 for arg in argv
        ):
            raise ProfileError("argv must be a bounded array of strings")
        if not _relative(cwd):
            raise ProfileError("cwd must be a safe relative path")
    return data


def read_profile(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ProfileError("profile path is missing or a symlink")
    if path.stat().st_size > MAX_PROFILE_BYTES:
        raise ProfileError("profile too large")
    try:
        return validate_profile(json.loads(path.read_text(encoding="utf-8")))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ProfileError("invalid UTF-8 or JSON") from exc
