# SF-07 — Portability and integration acceptance contract

Status: **SF-07 portability fixture acceptance completed for PR #12** on native Linux and Windows/Python 3.12. **CI-13 enforced required checks, qualified by PR #15's actual successful merge group and PR #16's controlled failing/skipped queue rejection.** This qualifies the s-f repository's CI acceptance boundary, not a complete production Software Factory.

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
| Symlinked destination | Proposed writes blocked when a link targets a different directory; a platform skip means the symlink capability is NOT qualified unless separately tested; CI-13 now rejects all unittest skips |
| Stale plan / altered instructions | Fresh preconditions reject modified targets; no silent replacement |
| Upgrade with local edit | Reports conflict, keeps edited owned content and project data |
| Crash/interruption | Journal blocks new effects, checked recovery is idempotent, forged or unexpected intermediate state fails closed |
| Existing custom project CI | No new competing workflow installed in target project |

## Historical portable-installation evidence (G2 fixtures)

PR #12 was squash-merged to main at `5bc3c39c887d24cd7b03f348285af5a5d955386c`, preserving the reviewed file blobs. The exact candidate head `5d2cd4fc015a174fddd7b507f5cd9ba189900420` passed [GitHub Actions run 37761747633](https://github.com/spsoftwarefc/s-f/actions/runs/37761747633) attempt 1, `pull_request` event. Ubuntu 24.04 / Python 3.12.14: **61 tests OK** (job `113259575335`). Windows 2022 / Python 3.12.10: **61 tests OK** (job `113259575053`). The earlier Windows run failed on platform-specific test fixtures; those were corrected. These are **PR-head fixture outcomes**, not a historical proof that GitHub required the checks before the merge.

No `merge_group` workflow run was observed during PR #12 integration. No required status checks were configured in the Base ruleset at that time. Thus the two native successes do **not** establish enforced future CI gates or a verified merge-group check. The exact historical source and limitations are documented in `docs/factory/evidence/SF-07.md`.

## CI-13/CI-16 completed repository CI enforcement evidence

The historical PR #12 result above is not retroactively transformed into a merge-group pass. The **subsequent** CI-13 implementation was consolidated into GitHub queue-squash-merged [PR #15](https://github.com/spsoftwarefc/s-f/pull/15), final main SHA `eea5b503990e20167b2d88073f0d9e79c2990378`. Its actual [merge_group run 37770656384](https://github.com/spsoftwarefc/s-f/actions/runs/37770656384) checked out the same commit SHA and tree `3dfe90c36e5116d7d804ca69c09e819572536210`, with **71/71 tests on Linux and Windows**, zero skipped tests, and the dependent `sf07-acceptance` job successful. Independent [PR run 37770487614](https://github.com/spsoftwarefc/s-f/actions/runs/37770487614) also passed, on its separate PR merge-ref revision.

Live Base ruleset [24705576](https://github.com/spsoftwarefc/s-f/rules/24705576) binds the named Linux/Windows/acceptance checks to GitHub Actions app `15368`, with required pull requests, zero reviewer approvals, squash merge queue (minimum group **1**, wait **3 minutes**), no bypass actors, and non-fast-forward/deletion protection. These rules are **for s-f** and are not imposed on arbitrary downstream repositories.

PR #15's controlled [negative PR-stage run 37770394865](https://github.com/spsoftwarefc/s-f/actions/runs/37770394865) blocked a failing candidate. PR #16's controlled [negative merge_group run 37772265905](https://github.com/spsoftwarefc/s-f/actions/runs/37772265905) recorded **Linux failure**, **Windows job skipped**, and **unconditional acceptance failure**. GitHub removed PR #16 from the merge queue and `main` remained unchanged. Temporary event-only probes were **restored byte-for-byte** before final promotion; they are not permanent CI policy. Full provider event/tree/job evidence appears in `docs/factory/evidence/CI-16.md`.

The exact provider behavior of cancelled, missing/unreported, neutral and superseded queue checks was not separately provoked. Those conclusions must not be claimed experimentally verified; the source-based acceptance predicate rejects non-success prerequisites. No release, downstream branch protection, deployment or operational qualification follows from this result.

## Scope and trust limit

The portable factory's universal promotion rule is successful evidence for the **current integration candidate**, enforced by the target project's actual supported promotion mechanism. A GitHub merge queue, check contexts and this platform matrix are specific to the s-f repository and are **not universal installation defaults**.

The source code and local journal do not establish authenticated distribution, adversarial filesystem isolation, downstream CI enforcement, command execution safety or production deployment readiness. Follow-on SF-08–SF-19 packages remain separate. Operator review of a changed workflow/checker is procedural, not independently enforceable against an administrator or a candidate that modifies its own gate.
