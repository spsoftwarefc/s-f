"""Read-only bounded repository inventory.

Inventory is discovery, not proof that a command or external control is enforced.
"""
from __future__ import annotations

import json
from pathlib import Path

MARKERS = {
    "pyproject.toml": "python",
    "package.json": "node",
    "Cargo.toml": "rust",
    "go.mod": "go",
}
INSTRUCTIONS = {"AGENTS.md", "CLAUDE.md", "SKILLS.md"}
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "dist", "build", "__pycache__"}
MAX_FILES = 25000
MAX_DEPTH = 12


class InventoryError(ValueError):
    pass


def inventory(root: Path) -> dict:
    if not root.is_dir() or root.is_symlink():
        raise InventoryError("repository root must be an existing non-symlink directory")
    root = root.resolve(strict=True)
    pending = [(root, 0)]
    files = []
    while pending:
        current, depth = pending.pop()
        if depth > MAX_DEPTH:
            raise InventoryError("repository nesting limit exceeded")
        try:
            entries = sorted(current.iterdir(), key=lambda p: p.name)
        except OSError as exc:
            raise InventoryError("unreadable repository path") from exc
        for entry in entries:
            if entry.is_symlink():
                continue
            rel = entry.relative_to(root).as_posix()
            if entry.is_dir():
                if entry.name not in SKIP_DIRS:
                    pending.append((entry, depth + 1))
            elif entry.is_file():
                files.append(rel)
                if len(files) > MAX_FILES:
                    raise InventoryError("repository file limit exceeded")
    manifests = sorted(x for x in files if Path(x).name in MARKERS)
    instructions = sorted(x for x in files if Path(x).name in INSTRUCTIONS)
    workflows = sorted(x for x in files if x.startswith(".github/workflows/") and x.endswith((".yml", ".yaml")))
    components = [
        {"path": p, "stackHint": MARKERS[Path(p).name]}
        for p in manifests
    ]
    return {
        "schemaVersion": 1,
        "root": root.as_posix(),
        "components": components,
        "instructionFiles": instructions,
        "workflowFiles": workflows,
        "commandsExecuted": [],
        "releaseReady": False,
        "limits": {"maxDepth": MAX_DEPTH, "maxFiles": MAX_FILES},
        "unknowns": ["authoritative commands", "CI enforcement", "deployment capabilities"],
    }
