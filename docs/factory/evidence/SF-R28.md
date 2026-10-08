# SF-R28 — Post-PR #28 protected integration reconciliation

**Record type:** source-bound, read-only documentation and provider-evidence reconciliation. This record describes *already completed* historical GitHub events. It does not attest the outcome of this reconciliation PR's own future checks or grant production/release authority.

## Baseline and work-order sequencing

- Repository: `spsoftwarefc/s-f`, protected `main` integration baseline `ad573a2d900d4fef8211455ab9512e4a8003ac17`, Git tree `c3f07bc882770abb795af7fe14bc414552cb2fe3`. This is [PR #28](https://github.com/spsoftwarefc/s-f/pull/28)'s confirmed protected merge commit, not its pre-queue source head.
- Initial candidate declaration: `docs/factory/work-orders/SF-R28.json` at independently committed `4596671edaa680c4443be7b574c4460af46d74b3`, before any README/PROJECT/REQUIREMENTS implementation edits. Allowed scope: this evidence file, the work order, and exactly those three existing documents.
- PR #28 source head: `2c1c319b2cc9f1799b68ff9c6680c1a7f93f701e`. Git tree `c3f07bc882770abb795af7fe14bc414552cb2fe3` matches the final protected merge commit tree exactly. This shows content incorporation, **not** preservation of all predecessor individual commit identities in squash-merged `main`.

## Observed protected PR #28 integration

- [Merge-group GitHub Actions run #37840817630](https://github.com/spsoftwarefc/s-f/actions/runs/37840817630): `event=merge_group`, attempt 1, conclusion `success`; exact queue SHA `ad573a2d900d4fef8211455ab9512e4a8003ac17`, tree `c3f07bc882770abb795af7fe14bc414552cb2fe3`, base SHA `6c82b1230046650afcf28a61d7c8da7f8d157773`.
- Required Linux `sf07-portability (ubuntu-24.04, py3.12)` job `113529425124`: `success`, 332 discovered/executed, zero failures/errors/skips (from observed job log).
- Required Windows `sf07-portability (windows-2022, py3.12)` job `113529424616`: `success` (provider job record). Its prior PR-stage exact-source suite also passed 332/332; do not substitute PR-stage evidence for merge-group evidence.
- Required `sf07-acceptance` job `113530461509`: `success`.
- GitHub PR #28 `merged=true`, `merge_commit_sha=ad573a2d900d4fef8211455ab9512e4a8003ac17`, merged at **2026-10-08T20:40:27Z** by protected squash merge. The `main` ref was subsequently read and independently confirmed at that exact commit.
- PRs #23, #24, #25, #26 and #27 are now `closed`, `merged=false`, annotated with separate **incorporated through PR #28** records; they were **not** individually merged. Following the cleanup, the repository had zero open PRs and only `main` plus `governance/ci-enforcement-13` remained as branches at this reconciliation baseline (a new post-merge documentation PR is expected to open separately).

## Actual documentation change and preservation review

- BEFORE: `README.md` asserted the SF-19 cumulative PR was `not yet merged` and the predecessors were open; `docs/factory/PROJECT.md` and `docs/product/REQUIREMENTS.md` repeated pending PR #28 and outstanding SF-13I source incorporation.
- AFTER: all three state the observed protected merger, correct head/base/tree/job evidence, and predecessor administrative closure. Historical PR #12/#22 evidence remains identified as prior checkpoints.
- `docs/factory/SF19_QUALIFICATION.md`, `docs/factory/evidence/SF-19.md` and original package work orders are **not overwritten**; they preserve pre-merge plans/evidence. This new file is the later factual reconciliation.
- Scope excludes `.github/**`, `src/**`, `tests/**`, branch protection, target repositories and deployment systems. No source/CI runtime commands were executed during documentation editing and **no new product behavior or release permission is claimed**.

## Residual governance branch audit

- `governance/ci-enforcement-13` at `d4dc3c15052bf2e090e923a32ba1f0cbd8bfc37f` is the already-closed, separately unmerged PR #14's historical head. That exact head is a Git ancestor of PR #15's source head `462deb900a7e2124daff05e81e08f54abbbe65cc`; PR #15 was protected squash-merged at `eea5b503990e20167b2d88073f0d9e79c2990378` and its source tree matches the merge tree `3dfe90c36e5116d7d804ca69c09e819572536210`.
- No open PR depended on the old branch at baseline. This demonstrates suitability for **optional administrative deletion**, subject to GitHub permissions and explicit action. **No deletion has occurred in this package.** The active GitHub connector does not expose a branch-ref deletion tool; it would be inaccurate to claim successful deletion by changing the ref or deleting a file.

## Unqualified product/release scope

Source integration and exact CI provider checks do not verify genuine publisher signatures or authenticated trust-pin provisioning, independently custodied release approvals, real external deployment, disk-durable multi-process recovery, or live observations and incident handling. SF-17 and SF-18 remain deferred; SF-R10 remains unmet. No public production v1 acceptance, external installation, notification, execution, deployment or authorization is asserted.

## Candidate/CI evidence boundary

This document is committed *before* opening the post-merge reconciliation PR. It does not claim its own hosted checks have passed. Provider validation and queue records for that subsequent documentation candidate belong to the exact PR and future post-merge evidence. Do not rerun the unchanged source merely for a presentation metric.
