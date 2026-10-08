# s-f repository factory adapter

Status: SF-07 portable installation qualified on prior PR-head Linux/Windows tests; CI-13 live merge-queue enforcement pending.
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

## Current merge cadence

PR #12 consolidated SF-01–SF-07 and merged to `main` at `5bc3c39c887d24cd7b03f348285af5a5d955386c`. PRs #6–#11 were closed as superseded. The next prerequisite is CI-13, tracked in Issue #13: a focused PR for unconditional acceptance plus a separately verified live ruleset requiring Linux, Windows and acceptance contexts. Do not merge a future PR merely because code-level gate changes pass; the Base ruleset and merge-group integration must be qualified. Squash commits preserve final files but not intermediate source commit ancestry.

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

The CI-13 candidate uses distinct PR and merge-group event checks for Linux, Windows and an explicit acceptance job. No continuous push or self-hosted workflow is added. The limiting resource is hosted execution, not repository storage. During implementation:

1. run focused tests locally/tool-side;
2. run the applicable local acceptance suite once on a stable candidate;
3. trigger hosted CI only when it is required for a provider-specific claim;
4. reuse valid exact-candidate evidence rather than rerunning unchanged jobs;
5. never treat a skipped or unavailable hosted check as success.

Self-hosted CI is not part of SF-07 and is not placed on a production VPS by default.

## Current package

`docs/factory/work-orders/CI-13.md` defines the current governance correction; `docs/factory/CI_ENFORCEMENT.md` defines the project-specific required check contexts, strict skip policy, provider identity and outstanding ruleset work. The present CLI supports profile validation, inventory, installation planning and managed local lifecycle. SF-08–SF-19 implementation remains pending.
