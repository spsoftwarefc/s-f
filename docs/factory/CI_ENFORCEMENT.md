# CI-13 — Required-check enforcement and integration identity

Status: **three required GitHub Actions contexts verified in active Base ruleset; merge-group integration and negative provider enforcement remain UNVERIFIED** (2026-10-08).
Scope: the `spsoftwarefc/s-f` repository. This is a repository-specific implementation of a portable promotion rule, not a requirement that every installed factory use GitHub, this matrix or these job names.

## Universal promotion contract

Acceptance requires **successful evidence for the current integration candidate** and enforcement by the destination project's supported promotion mechanism. Installation and a green local test run do not configure branch rules or authorize release.

## Repository-specific required contexts

The active `main` ruleset is [Base](https://github.com/spsoftwarefc/s-f/rules/24705576). Preserve deletion protection, non-fast-forward protection, squash merge queue and no bypass actors. The Base ruleset NOW HAS GitHub's **require status checks** rule, with the exact three job names (case and punctuation matter):

1. `sf07-portability (ubuntu-24.04, py3.12)`
2. `sf07-portability (windows-2022, py3.12)`
3. `sf07-acceptance`

Live reread at 2026-10-08 14:24 EAT confirmed all three contexts bound to **GitHub Actions integration 15368**, strict checks enabled, no bypass actors, pull requests required with zero approvals, and deletion/non-fast-forward plus squash merge queue retained. This is provider configuration evidence, not yet an actual merge-group enforcement test. The connected GitHub connector exposes ruleset **reads**, but no write operation.

The separately named Linux and Windows jobs remove ambiguity from one aggregate matrix `needs` result. The acceptance job declares `needs: [linux, windows]` and `if: always()`; it passes only when **both dependency results equal `success`**. A skipped, neutral, failed, missing or cancelled required job does not qualify the factory acceptance claim. GitHub may regard `skipped` or `neutral` as acceptable for individual required checks; requiring the successful acceptance job adds a fail-closed dependency predicate. This does not protect against someone deleting or editing the acceptance job without a separate controlled review.

**Individual tests:** the mandatory discovery suite accepts **zero skipped tests**, expected failures, unexpected successes, test load errors or assertion failures. It also verifies at least 61 discovered cases, the declared baseline critical-test inventory, and **executed test count exactly equal to the discovered count**; both fewer and more executions fail qualification. Inability to create platform-specific test fixtures (for example symlinks) is a **qualification failure for that platform**, not green evidence. A future explicit policy exception must identify scope, excluded capability and an approved alternate proof, and must not label the excluded capability qualified. Changes to required test names/count are gate changes requiring operator review; the local inventory is not independently tamper-proof.

## Event and revision identity

GitHub Actions executes on `pull_request` and `merge_group`, not duplicate `push` events. Each platform job prints and verifies:

- `GITHUB_EVENT_NAME`, `GITHUB_REF`, `GITHUB_SHA`.
- `GITHUB_WORKFLOW`, `GITHUB_WORKFLOW_REF`, `GITHUB_RUN_ID`, `GITHUB_RUN_ATTEMPT`, `GITHUB_JOB`.
- Actual `git rev-parse HEAD` and `git rev-parse HEAD^{tree}`, with actual commit required to equal `GITHUB_SHA`.
- For PR events: `pull_request.head.sha` and `pull_request.base.sha`.
- For merge-group events: `merge_group.head_sha` and `merge_group.base_sha`.

A separate provider inspection records workflow file identity, numerical **job IDs**, conclusions, exact run URL, run attempt and source app from the GitHub API, since numerical job IDs are not available simply from `GITHUB_JOB`. Compare checks to the exact tested SHA/event; don't reuse stale or superseded head results.

A PR check often tests an ephemeral `refs/pull/.../merge` commit rather than the literal PR head. A merge-group check tests another temporary SHA representing queued integration. Following the merge, record the final squash commit, its parent, tree and diff/provenance relationship to the successful tested candidate. **SHA equality between a squash merge and a PR head or queue head is not required.** A queue run cannot be inferred from a successful PR run; inspect it separately. Identical file tree, if observed, supports content identity but does not prove identical commit identity or merge policy.

## Control-change review boundary

Before promoting a candidate that changes `.github/workflows/**`, `tools/ci_acceptance.py`, `tests/**`, `docs/factory/**` gates, or test inventory, the operator records the old/new diff and explicitly checks: deleted/renamed assertions, new conditional skips/xfails, relaxed inventory thresholds, softened error paths, dependency gating/always semantics, action SHA revisions, new permissions/secrets and provider context renames. This is **procedural operator review** for a solo repo, not independent external technical enforcement against an administrator or candidate-controlled checker.

Baseline supply-chain minimum: read-only `contents: read`; pinned `actions/checkout` and `actions/setup-python` by immutable full SHA; `persist-credentials: false`; bounded job timeouts; no release secrets in PR jobs. Deeper dependency scan/attestation is conditional on actual dependency, tool or trusted action changes; these standing controls are not optional.

## Provider qualification before closing Issue #13

1. Finish a focused PR without bypassing branch controls; capture exact successful Linux, Windows and acceptance run/job data on its final SHA. A PR-only success is insufficient for a merge queue assertion.
2. **Verified**: re-read live Base required contexts and GitHub Actions app source, keeping the queue intact. Code Quality rule was removed; no additional unqualified analyzer gate remains.
3. Use the focused, nonproduction PR #15 qualification candidate under the user-authorized PR #15 merge boundary to observe successful `merge_group` checks. At current queue settings minimum group size is 2 and wait 10 minutes; after this wait GitHub permits a single entry, so do not create an unrelated filler PR. Queue entry can automatically merge; **do not enqueue** unless that merge is authorized.
4. Exercise genuine provider blocking with a controlled failing required context. Verify missing/cancelled/skipped and superseded cases where provider-safe; negative unit tests alone do **not** prove GitHub enforcement. Never invent a skipped provider check.
5. Reconcile the exact merged commit and integration-candidate relationship. Close Issue #13 only after provider and ruleset checks are demonstrably satisfied. Otherwise keep it open, with unknowns documented.

No mandatory human approval count, paid reviewer, parallel duplicate push runs or self-hosted production machine is introduced. Larger reusable CI evidence verification remains in SF-10 and later packages.