# SF-04 — Declared project profile and adapter contracts

Status: development preview; syntax is versioned by `schemaVersion: 1`.
This contract extends the SF-02 bootstrap without executing any project command or altering its tools.

## Profile shape

```json
{
  "schemaVersion": 1,
  "project": {"id": "example"},
  "commands": {
    "test": {
      "argv": ["python", "-m", "unittest", "discover"],
      "cwd": ".",
      "risk": "build",
      "network": false,
      "timeoutSeconds": 120
    }
  },
  "components": [
    {"id": "service", "path": ".", "stack": "python", "dependsOn": [], "checks": ["test"]}
  ]
}
```

`components` is optional for compatibility with SF-02 bootstrap profiles. Component stacks: `python`, `node`, `rust`, `go`, `custom`. A custom build needs no language parser: it supplies its own command array.

All command names and component names are bounded identifiers. Paths use slash-separated repository-relative segments. `.` is the explicit project root; absolute paths, backslashes, `..`, embedded `.` and empty segments are prohibited. Root-aware validation additionally checks that declared directories exist, are directories and do not cross symlinks. Pure profile validation deliberately does not claim those filesystem checks have run.

`dependsOn` and `checks` are optional arrays. Dependencies are component IDs; checks reference defined commands. Graphs must be acyclic and every reference must resolve. Command `risk`, `network` and `timeoutSeconds` are descriptive metadata for a future qualified runner, not enforced isolation controls.

## Read-only commands

```sh
sf profile validate path/to/profile.json
sf profile validate path/to/profile.json --root path/to/repository
sf profile plan path/to/profile.json --root path/to/repository
```

`sf profile plan` emits deterministic dependency-first component/check declarations. It never executes `argv`, installs packages or contacts the network. `sf doctor` continues reporting `releaseQualified: false`.

Adapter hints for known stacks are explicitly non-authoritative: the user/project profile defines the actual commands. This prevents replacing a project's package manager or custom CI. Installation planning belongs to SF-05, execution to SF-09, and CI verification to SF-10.

## Compatibility and enforcement boundary

SF-02 profiles using `schemaVersion`, `project` and `commands` remain accepted. The one intentional refinement is `cwd: "."`, which designates the project root without traversal. This is not a relaxed parent-directory escape. Existing project dependencies and runtime code are not changed.

A passing schema validator proves only bounded configuration structure, not tool availability, command safety, CI enforcement, production readiness or an authorized release.
