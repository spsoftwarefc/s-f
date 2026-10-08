# s-f repository factory adapter

Status: SF-07 candidate qualification (G2 not yet accepted).
Authority: this file configures the reusable workflow for the `spsoftwarefc/s-f` repository. It grants no authority over repositories where s-f may later be installed.

## Purpose

Build and qualify a portable, repository-local software factory that supports a developer or coding agent from planning through deployment while preserving each target project's own requirements, architecture, tests, CI and release authority.

The CTJ bot is an extraction source only. Trading contracts, stage ledgers, exchange procedures, account credentials, venue qualification and historical completion records are outside this repository's authority.

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

SF-00 is merged into `main` at the reconciled baseline. Current stack: PRs #6–#11 with planned PR #12 as the acceptance and merge boundary. Work is staged on dependent branches; no interim merge before final combined acceptance. Repository ruleset mandates a merge queue and squash integration; follow it, do not bypass it or claim intermediate history survives a squash.

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

The SF-07 candidate introduces a one-event PR/merge-queue matrix for required Linux/Windows evidence. No continuous push or self-hosted workflow is added. The limiting resource is hosted execution, not repository storage. During implementation:

1. run focused tests locally/tool-side;
2. run the applicable local acceptance suite once on a stable candidate;
3. trigger hosted CI only when it is required for a provider-specific claim;
4. reuse valid exact-candidate evidence rather than rerunning unchanged jobs;
5. never treat a skipped or unavailable hosted check as success.

Self-hosted CI is not part of SF-07 and is not placed on a production VPS by default.

## Current package

`docs/factory/work-orders/SF-07.md` defines the active portability acceptance. The present CLI validates/inventories/plans and conditionally applies/reconciles owned files; later SF-08–SF-19 packages implement the development lifecycle, authoritative CI proof, security, distribution and release/deployment capabilities.
