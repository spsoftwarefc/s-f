# s-f repository factory adapter

Status (8 October 2026): SF-00–SF-13 are incorporated through protected PR #22 at `6c82b1230046650afcf28a61d7c8da7f8d157773` (tree `d95b8fc15c358992961e98d0adeb9f90dd07db09`). Merge-group run 37801503467 passed Linux, Windows and `sf07-acceptance`. Publisher signatures, authenticated trust-pin provisioning and production release remain unqualified; the SF-13I installer binding is in the pending PR #24–#28 stack, not yet incorporated into main.
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

## Incorporated baseline and pending cumulative qualification

SF-08–SF-13 are integrated through protected PR #22. `docs/factory/work-orders/SF-R22.json` and `docs/factory/evidence/SF-R22.md` preserve the historical post-merge reconciliation.

As of 8 October 2026, **PRs #23–#27 remain stacked and unmerged**. Their implemented and PR-stage tested candidates provide reconciliation (#23), exact externally-pinned archive byte installation (#24), offline artifact/release planning (#25), fake-target deployment/recovery (#26) and offline operational incident/work proposals (#27). The sole next planned mainline integration is **PR #28**, carrying SF-19 cross-package development qualification and source-history reconciliation. Required cumulative PR checks and protected merge-group validation must be observed, not inferred from earlier runs.

Important distinctions: a matching trust pin does not authenticate its issuer; SF-14 cannot authorize an actual release; SF-15 is in-memory simulated dispatch/recovery; SF-16 has no live telemetry or incident ownership. Production v1 readiness remains **blocked**, even if protected source incorporation passes. SF-17/18 and SF-R10 budget/orchestration remain deferred. No target-project installation, external release, deployment, real recovery, or production activation is authorized.

See `docs/factory/SF19_QUALIFICATION.md` and `docs/factory/evidence/SF-19.md` for acceptance ladder, blocked claims and cumulative evidence.
