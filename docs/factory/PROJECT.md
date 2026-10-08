# s-f repository factory adapter

Status (8 October 2026): SF-07 portability/required CI are merged and historically qualified. SF-08 through SF-13 are implemented as a currently unmerged PR #17–#22 stack, with PR #22 reserved for cumulative integration qualification. Distribution verification matches a separately provisioned exact digest pin; signed publisher identity, authenticated trust provisioning, enforced installation lock and production release remain unqualified.
Authority: this file configures the reusable workflow for the `spsoftwarefc/s-f` repository. It grants no authority over repositories where s-f may later be installed.

## Purpose

Build and qualify a portable, repository-local software factory that supports a developer or coding agent from planning through deployment while preserving each target project's own requirements, architecture, tests, CI and release authority.

## Operating rules

- One implementation package is active at a time unless explicitly authorized otherwise.
- Every implementation package starts with a committed work order.
- Prefer local or ChatGPT-side verification during development.
- Use GitHub-hosted Actions only when a hosted run proves a claim that local verification cannot.
- Do not duplicate push and pull-request runs merely for presentation.
- No reviewer request or approving-review count is a factory acceptance prerequisite.
- Merge and deployment remain separate effects requiring the user's active cadence/authorization.
- Missing evidence is unknown, not success.

## Repository integration history and authority

- PR #12 merged the SF-00–SF-07 portable installation foundation at `5bc3c39c887d24cd7b03f348285af5a5d955386c`.
- PR #15 consolidated the CI-13/CI-15 source and was squash-merged by the GitHub queue to `main` at `eea5b503990e20167b2d88073f0d9e79c2990378`. PR #14 was closed as superseded, not merged separately.
- The live Base ruleset `24705576` requires pull requests with **zero approving reviews**, three named GitHub Actions checks (Linux, Windows and `sf07-acceptance`, provider id `15368`), a squash merge queue (minimum 1), non-fast-forward/deletion protection, and no bypass actors.
- PR #15 [successful merge-group run 37770656384](https://github.com/spsoftwarefc/s-f/actions/runs/37770656384) validated the exact mainline commit/tree. PR #16 [negative merge-group run 37772265905](https://github.com/spsoftwarefc/s-f/actions/runs/37772265905) showed a controlled Linux failure, Windows skipped job, failing acceptance, and actual queue removal with `main` unchanged. The temporary probe was restored byte-for-byte.
- PR #16 subsequently merged at `9178dd0d6e0f0dee49d1b4f693bdf8d5f59ff2c5`, after successful real merge-group run [37773194423](https://github.com/spsoftwarefc/s-f/actions/runs/37773194423) (attempt 1). Its final tree `6d89e8fc5721a915891b91e9cd72fade41c62c4d` is the SF-08 baseline.
- PR #22 [protected merge-group run 37801503467](https://github.com/spsoftwarefc/s-f/actions/runs/37801503467) succeeded on integration SHA `6c82b1230046650afcf28a61d7c8da7f8d157773`, tree `d95b8fc15c358992961e98d0adeb9f90dd07db09`; Linux, Windows and `sf07-acceptance` jobs concluded success. GitHub reports PR #22 merged at 2026-10-08 15:33:58 UTC; this exact SHA is `main` at reconciliation baseline. PRs #17–#21 were closed as incorporated, not individually merged.
- Provider outcomes for cancelled, missing, neutral or superseded queue checks have not been separately induced. Claim only the successful integration and failed/skipped rejection actually witnessed. Documentation contracts do not replace a platform-enforced gate.

## Instruction ownership

| Location | Owns |
| --- | --- |
| `AGENTS.md` | Repository entry point and operating boundaries |
| `SKILLS.md` | Selection of repository-local factory skills |
| `.agents/skills/` | Single-source skill bodies |
| `docs/factory/WORKFLOW.md` | Reusable production lifecycle |
| `docs/factory/WORK_ORDER.md` | Work-package checkpoints and evidence expectations |
| `docs/factory/PROJECT.md` | s-f-specific configuration and authority boundary |
| `docs/factory/work-orders/` | Package declarations and package-specific acceptance |
| `docs/factory/EXTRACTION.md` | Source provenance and import classification |

`CLAUDE.md` and later host adapters remain thin references to `AGENTS.md`; they do not copy policy bodies.

## Resource policy

The enforced CI-13 workflow uses separate PR and merge-group events for Linux, Windows and the dependent acceptance job. No continuous push or self-hosted workflow is added. The limiting resource is hosted execution, not repository storage. During implementation:

1. run focused tests locally/tool-side;
2. run the applicable local acceptance suite once on a stable candidate;
3. trigger hosted CI only when it is required for a provider-specific claim;
4. reuse valid exact-candidate evidence rather than rerunning unchanged jobs;
5. never treat a skipped or unavailable hosted check as success.

Self-hosted CI is not part of SF-07 and is not placed on a production VPS by default.

## Incorporated development-factory packages and pending qualification

SF-08–SF-13 are incorporated through PR #22, not an open PR stack. The post-merge reconciliation work order is `docs/factory/work-orders/SF-R22.json` and its evidence is `docs/factory/evidence/SF-R22.md`. This documentation pass does not retroactively upgrade the historical package evidence to product release qualification.

- SF-08 — Git-history work-order start/resume; SF-09 — bounded execution receipts; SF-10 — provider-metadata CI evidence; SF-11 — read-only assurance/review; SF-12 — offline security/dependency adapters; SF-13 — deterministic bundle plus separately pinned digest/compatibility verification.
- Critical outstanding boundary: SF-06 installation/upgrade does not enforce SF-13 distribution/lock verification, so installed bytes are not proven to match externally authenticated distribution bytes. A checksum alone is not signed publisher provenance; no authenticated trust-pin issuance channel is attested.
- Next stacked PR sequence: #23 post-merge reconciliation, #24 SF-13→SF-06 enforcement, #25 SF-14 artifact/release planning, #26 SF-15 deployment/recovery qualification, #27 SF-16 operations/feedback, #28 SF-19 v1 qualification/cumulative integration. Numbers #24–#28 are planned, not implemented or automatically authorized to merge.
- SF-17/18 optional agent/orchestration work is deferred. No installation into other projects, hosted orchestrator, publication, release or production deployment is authorized by package incorporation or a successful GitHub merge.
