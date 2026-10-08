# SF-08 — Offline planning and work-order assessment

Status: implementation candidate. Contract version: `schemaVersion: 1`.

A JSON work order is committed in an isolated first commit, before implementation. The canonical human checklist remains `WORK_ORDER.md`, and existing project contracts remain authoritative.

## Usage

```sh
sf work start --root . --order docs/factory/work-orders/SF-08.json --base-ref main
sf work resume --root . --order docs/factory/work-orders/SF-08.json --base-ref main
```

Both commands only invoke Git read operations. Exit 0 means no identified development blockers, not proof that obligations, CI or acceptance are complete. Exit 1 signals detected blockers; exit 2 reports malformed/unavailable input. Worktree changes are not cleaned, reset, staged or modified.

## Contract and evidence

The v1 declaration is a closed schema containing package ID, full baseline commit and tree IDs, objective, non-goals, allowed exact paths or suffix `/**` prefixes, requirements, decisions, structure, impact, obligations with typed proof kinds, dependencies, budgets, external effects, proof references and append-only amendments with reasons. The first declaration commit may modify only the order file. Each amendment requires a later isolated order-file commit and newly appended reason. A single first-parent Git history is inspected; merge-history ambiguity blocks validation rather than silently attesting precedence.

Git-ancestor dependencies can be established locally; external dependencies remain unknown. Development blockers prevent `developmentReady`; unknown dependencies scoped only to an external effect do not halt independent development. Out-of-scope committed and dirty paths, dirty declaration, stale base-ref and baseline tree mismatch are explicit findings. Documentation-only changes must declare preservation and diff-review proof kinds.

Proof references are inspected only for tracked presence. `presentUnverified` never means successful proof; `providerCI` and `accepted` always remain unknown. Only the existing project's authority and later SF-10/SF-11 can verify those claims. No mutable package-state ledger is created.

## Limitations

The Git status inspection requires a Git worktree root and Git executable. History checks use first-parent ancestry and report merge commits as needing review. Git ref drift is detected only when `--base-ref` is provided and locally available; fetch freshness is not asserted. Git object and metadata trust follow the local repository trust boundary. This does not enforce execution authorization for other tools or stop a person from editing the worktree. SF-09 implements execution receipts separately, SF-10 provider evidence, and SF-11 assurance.

No CI workflow changes and no external project or deployment effects are included.
