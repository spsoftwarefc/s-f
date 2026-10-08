# SF-07 — Portability and integration acceptance contract

Status: **candidate**, not automatically accepted by test-suite presence. This qualifies the **portable installation layer** (SF-00 through SF-07), not complete software production/release governance.

## G2 fixture scenarios

| Fixture | Intended proof |
| --- | --- |
| Empty/new repository | Generated owned files, read-only first plan, explicit apply, complete remove, no source overwrite |
| Existing Python service | Build scripts never executed during discovery, application bytes preserved |
| Existing Node UI and custom CI | Existing package, root and nested AGENTS instructions, CLAUDE and CI bytes preserved; manual routing acknowledged |
| Rust component | Cargo manifest preserved; no Python runtime modification of Rust component |
| Mixed monorepo | Project-owned Node/Python/Rust commands retained, dependency ordering checked, all original manifests unchanged |
| Custom/unknown build | Explicit commands or absent tests supported without inventing release qualification |
| Unicode/spaces/CRLF | Valid rooted path support and original byte preservation |
| Dirty/untracked content | Git dirty state remains unknown without a verified Git-status adapter, data untouched |
| Preexisting .s-f prefix / path collisions | Foreign namespace not adopted; case-insensitive collisions blocked |
| Symlinked destination | Proposed writes blocked when a link targets a different directory; platform inability to create a test symlink is reported as a test skip |
| Stale plan / altered instructions | Fresh preconditions reject modified targets; no silent replacement |
| Upgrade with local edit | Reports conflict, keeps edited owned content and project data |
| Crash/interruption | Journal blocks new effects, checked recovery is idempotent, forged or unexpected intermediate state fails closed |
| Existing custom project CI | No new competing workflow installed in target project |

## GitHub-hosted acceptance

The only new workflow is `.github/workflows/sf07-qualification.yml`. Trigger once for the stable PR #12 candidate via `pull_request`, and for the synthetic GitHub merge queue integration revision via `merge_group`. No duplicate `push` event, no scheduled runs and no release secrets.

Runner matrix: Ubuntu 24.04 and Windows 2022 with CPython 3.12. Checkout and Python setup actions are pinned to full SHA; checkout credentials are not retained. Jobs run pure stdlib source compilation and unit/integration fixture suites. The job has read-only repository permission and a 12-minute timeout. Native macOS is **unqualified**.

Report a pass only with actual linked provider job/run metadata, checked-out revision, attempt and successful jobs. A PR-head run does not prove the GitHub merge-queue integration revision; keep identities separate. If no hosted run is produced, or a job is cancelled/skipped/unavailable, Windows and integration claims remain **unknown** and G2 is blocked. Avoid rerunning an unchanged exact candidate for presentation.

## Boundary and acceptance decision

SF-07 does not provide an authenticated factory distribution, byte-level operating-system race resistance, multi-process lease, actual CI enforcement in downstream projects, project command execution, dependency scanning, independent reviewer requirements, artifact provenance, deployment or monitoring. These are later SF-08–SF-19 obligations. The local journal handles recoverable interruptions, not arbitrary concurrent hostile writers.

Repository ruleset currently mandates squash merge through a merge queue on `main`. Preserve that rule. The PR stack includes a work order committed before implementation per package, but a squash of the final integration PR will not preserve each intermediate commit in `main` history. The PR commit history and work-order evidence remain available in GitHub; do not misrepresent the mainline as retaining those commits.

SF-07 acceptance requires: completed local fixture suite with source identity; executed Linux and Windows Python-3.12 job successes; substantive review of the exact changed paths and controls; documented limitations; and GitHub's actual merge-queue authorization. Unavailable validation blocks rather than automatically waiving it.
