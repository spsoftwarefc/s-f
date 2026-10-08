# SF-05 — Installation plan contract

Status: development preview. The SF-05 planner is **read-only** and does not install anything.

## Command

```sh
sf integrate --dry-run --root /path/to/project --profile /path/to/project-profile.json
```

Output: deterministic JSON on stdout. Exit `0` means an unobstructed plan was produced, **not** that files were installed, CI checks passed, or a release is qualified. Exit `1` signals plan conflicts that require resolution. Exit `2` signals malformed inputs or unavailable prerequisites. The `--dry-run` flag is mandatory; `sf integrate --apply` does not exist until SF-06.

## Model

The planner reuses SF-03 repository inventory and SF-04 strict rooted profile validation, without executing discovered project commands. It returns:

- `schemaVersion`, `operation`, `projectId` and target root.
- `baseline.inventorySha256`: a hash of a bounded, normalized snapshot of discovered manifests, instructions, workflows and traversal limits. This is **not** a Git tree digest or an exhaustive dirty-worktree hash.
- `baseline.gitCommit`, `gitTree`, `dirtyPaths`: **null**, and `dirtyState`: `unknown` until a qualified local Git adapter provides evidence.
- `profileSha256`: canonical JSON profile digest, used for plan identity.
- `changes[]`: sorted candidate additions or no-op matches. Each entry includes target relative path, expected observed state/file digest, proposed UTF-8 content, desired SHA-256 and `add`/`unchanged`/`blocked` disposition.
- `conflicts[]`: sorted explicit path/reason entries.
- `preserved`: discovered instruction and workflow paths with declaration that native commands/data are untouched.
- `ci`: existing workflow paths and an explicit manual CI integration proposal; `writesPlanned` is always empty and `enforced` always false in this package.
- `installationAuthorized: false`, `filesWritten: []` and `releaseQualified: false`.

## Planned factory-owned files

- `.s-f/PROJECT.md`: generic project-local routing.
- `.s-f/INSTRUCTIONS.md`: portable factory guidance only.
- `.s-f/profile.json`: normalized validated profile (not a secret store).
- `.s-f/OWNERSHIP.json`: versioned ownership manifest listing the desired hashes of all other proposed factory-owned files.
- `AGENTS.md`: additive routing stub **only if absent**, or if recognized as already owned by exactly matching desired content and ownership manifest.

Existing `AGENTS.md`, `CLAUDE.md`, workflow YAML, dependencies, source and arbitrary project data are not modified. A pre-existing project-owned AGENTS file requires **manual routing review**; absence of that routing prevents an unqualified "ready" result. Custom workflows remain untouched, and no competing CI is silently installed.

A pre-existing `.s-f` directory cannot be adopted merely because it has the expected name. Matching previously generated ownership manifests are recognized for repeat-plan no-op; changed owned content produces a conflict. Foreign prefixes, case-fold collisions (for cross-platform safety), symlink paths, non-directory parents and oversized existing targets are blocked without following their contents.

## Trust and SF-06 boundary

Plans are **proposals**, not authority to mutate. Observations may go stale between planning and execution, and a filesystem can be modified concurrently. SF-06 must verify the expected source/profile identity, target path containment, symlink/collision behavior and current bytes at the actual apply point. A caller-supplied plan or an ownership manifest in a target repository must be treated as untrusted until qualified against an authentic factory bundle.

Do not put credentials or secrets inside project profiles: the proposed normalized profile appears inside the plan and future installed project files.

This first version does not generate project-specific instruction patches, Git dirty-path evidence, or CI workflow edits. It represents such cases as manual/unknown rather than claiming enforcement. SF-06 owns controlled application and SF-07 owns platform-specific integration qualification.

## SF-06 interface evolution

This document records the SF-05 **internal** `plan_install()` contract and its original dry-run JSON. Starting with SF-06, the public `sf integrate --dry-run` CLI wraps that planner with `plan_lifecycle()` and now emits the SF-06 before/local/after effect plan; the legacy JSON shape is not accepted as an apply document. Use `docs/factory/SF06_LIFECYCLE.md` for the current CLI format and the distinct `--apply` authorization step. The original SF-05 inventory and conflict rules remain inputs to lifecycle planning.
