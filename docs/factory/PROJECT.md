# s-f repository factory adapter

Status: SF-07 portable installation fixtures qualified; CI-13 required GitHub checks merged via PR #15 and real merge-group positive and CI-16 negative provider behavior verified. This remains a development-preview factory, not a production-qualified factory.
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
- The next integration is **PR #16 as a focused documentation/qualification closure**, not permission to begin SF-08 or to merge outside the user's next explicitly authorized boundary. Do not enqueue a final passing PR as an experiment: it can automatically merge.
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

## Current package

`docs/factory/work-orders/CI-16.md` defines the current narrow closure; `docs/factory/CI_ENFORCEMENT.md` and `docs/factory/evidence/CI-16.md` record enforceable contexts, strict skip policy, real queue proof and explicit limits. The present CLI supports profile validation, inventory, installation planning and managed local lifecycle. SF-08–SF-19 implementation remains pending.
