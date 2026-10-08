# CI enforcement — reusable promotion rule and s-f's GitHub qualification

Status: **s-f GitHub ruleset enforcement configured; passing and controlled failing/skipped `merge_group` cases observed**. This is a repository-specific CI governance control, not qualification of the entire Software Factory. Historical SHA/run evidence lives in `docs/factory/evidence/CI-15.md` and `docs/factory/evidence/CI-16.md`.

## Universal contract vs this project's provider

A production candidate is accepted only with successful evidence for the **current integration candidate**, enforced by the destination's supported promotion mechanism. A portable factory installation does **not** configure a destination's branch rules or authorize releases. GitHub Actions, this particular Python/OS matrix, and the merge queue are **s-f-specific**, not universal requirements on installed projects.

For `spsoftwarefc/s-f`, the active [Base ruleset](https://github.com/spsoftwarefc/s-f/rules/24705576), ID `24705576`, applies to `main`: pull request required with **zero approving reviews**, non-fast-forward and deletion protection, squash merge queue, zero bypass actors, and strict required status checks. The recorded October 8 configuration has `min_entries_to_merge=1`, 3-minute wait, `ALLGREEN` and three check contexts, all bound to GitHub Actions app `15368`:

- `sf07-portability (ubuntu-24.04, py3.12)`
- `sf07-portability (windows-2022, py3.12)`
- `sf07-acceptance`

Do not substitute descriptive strings for actual GitHub check names, weaken the source binding or silently add bypass actors. The former, unqualified code-quality rule was removed rather than represented as a verified analyzer. Repository-specific rulesets must be reread before each qualification if they may have changed.

## Strict acceptance semantics

The Linux and Windows jobs have **independent stable names**. The acceptance job declares `needs: [linux, windows]` and `if: always()`. It passes only when both dependency results are *exactly* `success`; `failure`, `skipped`, `cancelled`, unknown/empty or any other state is rejected. This is stronger than relying on GitHub's default interpretation of an individual skipped required job.

On each platform, the stdlib-only runner discovers tests, enforces minimum 61 tests, critical-test identities and **every discovered test executed exactly once** by count. Zero skipped tests, expected failures, unexpected successes, test errors and assertion failures are accepted. A capability missing on a host remains unqualified rather than silently receiving a pass. The runner and critical-test inventory are candidate-controlled: modifying them requires explicit operator source/diff review and cannot be treated as independent technical enforcement.

## Provider events and identities

The single pinned, read-only workflow `.github/workflows/sf07-qualification.yml` runs on `pull_request` and `merge_group` (not duplicate `push`), using Ubuntu 24.04 and Windows 2022 / Python 3.12. Checkout and Python setup actions are full-SHA-pinned; checkout does not persist credentials; job permissions are `contents: read`; timeouts are bounded. No release secrets or generic production runners are used.

Record the **separate** PR head/base SHA, checked-out PR synthetic merge SHA/tree, merge-group SHA/base/tree, workflow file reference, provider run ID/attempt, job IDs/conclusions/source app, and final squash commit/parent/tree. A PR head, PR synthetic merge, merge group and squash merge are distinct identities even when file trees match. A passing PR head is not proof of the queue; compare actual candidate identities, not green badges.

## Completed positive and negative qualification

**Positive integration (PR #15).** [Run 37770656384](https://github.com/spsoftwarefc/s-f/actions/runs/37770656384) was a real `merge_group` on queue SHA `eea5b503990e20167b2d88073f0d9e79c2990378`; Linux and Windows each ran 71/71 tests with zero skips/errors, and `sf07-acceptance` passed. The same SHA became the merged `main` commit with identical tree `3dfe90c36e5116d7d804ca69c09e819572536210`. [PR run 37770487614](https://github.com/spsoftwarefc/s-f/actions/runs/37770487614) independently exercised the final PR integration candidate.

**Negative PR-stage (PR #15).** [Run 37770394865](https://github.com/spsoftwarefc/s-f/actions/runs/37770394865) verified controlled test failures in both platform jobs and the dependent acceptance job; GitHub reported PR `mergeable_state=blocked`. The temporary failing source was removed before merging.

**Negative queue-stage (PR #16 controlled probe).** [Run 37772265905](https://github.com/spsoftwarefc/s-f/actions/runs/37772265905), event `merge_group`, showed real **Linux `failure`**, **Windows job `skipped`**, and unconditional `sf07-acceptance` **`failure`**. Its log recorded `linux=failure, windows=skipped, qualified=false`. GitHub logged `removed_from_merge_queue` at 11:46:52 UTC, and `main` did not move. The probe was injected only into the candidate, **not merged**, and the original workflow blob `89054cae40ac8215358d14bc2525c024ab499e9e` was restored byte-for-byte. Exact IDs, SHA/tree and timeline are recorded in `docs/factory/evidence/CI-16.md`.

These events directly prove working positive queue validation and rejection of a failing/skipped required-job merge group. They do **not** prove every possible provider fault. Provider-only **cancelled**, **missing/unreported**, **neutral**, and **superseded** queue scenarios were not separately executed; do not label them witnessed. The strict source-level acceptance predicate rejects non-success dependencies, but GitHub provider behavior for those particular scenarios remains an explicit qualification limit. Avoid fabricating checks or incurring long provider timeouts just for appearance of complete coverage.

## Control-change review, release boundary and resource discipline

Review every candidate diff touching `.github/workflows/**`, `tools/ci_acceptance.py`, `tests/**`, or instruction/gate contracts for deleted assertions, new skips, softened errors, source-app or context renames, privileges/secrets, new action revisions, branch-rule changes and expected-oracle drift. Solo-operator review is procedural, not a second-person requirement and not tamper-proof against administrators or a candidate that rewrites its own checker.

Use targeted local verification before one final exact-revision hosted pass. Only enter the merge queue when the operator has authorized that merge boundary; green queue checks can auto-merge. Separate code acceptance, merge, artifact/release qualification and production deployment. Generalized CI receipt verification and post-release assurance remain later SF packages, not outcomes of CI-13/CI-16.
