# s-f repository factory adapter

Status (8 October 2026): the development-source factory through SF-19, including SF-13I and SF-14–SF-16, is incorporated into protected `main` via PR #28 at `ad573a2d900d4fef8211455ab9512e4a8003ac17` (tree `c3f07bc882770abb795af7fe14bc414552cb2fe3`). Required Linux, Windows and `sf07-acceptance` passed in merge-group run 37840817630 before GitHub's protected squash merge. Publisher signatures, authenticated trust-pin provenance, actual deployment and durable/live operations remain unqualified; source integration does not authorize public/production release.
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
- PR #22 [protected merge-group run 37801503467](https://github.com/spsoftwarefc/s-f/actions/runs/37801503467) succeeded on integration SHA `6c82b1230046650afcf28a61d7c8da7f8d157773`, tree `d95b8fc15c358992961e98d0adeb9f90dd07db09`; Linux, Windows and `sf07-acceptance` jobs concluded success. GitHub reports PR #22 merged at 2026-10-08 15:33:58 UTC; this exact SHA was `main` at the earlier PR #22 reconciliation baseline. PRs #17–#21 were closed as incorporated, not individually merged.
- PR #28 [protected merge-group run 37840817630](https://github.com/spsoftwarefc/s-f/actions/runs/37840817630) passed Linux (job `113529425124`), Windows (`113529424616`) and dependent `sf07-acceptance` (`113530461509`) at exact queue SHA `ad573a2d900d4fef8211455ab9512e4a8003ac17`, tree `c3f07bc882770abb795af7fe14bc414552cb2fe3`. GitHub reports [PR #28](https://github.com/spsoftwarefc/s-f/pull/28) protected squash-merged at 2026-10-08 20:40:27 UTC; `main` advanced to that exact SHA. Its source head `2c1c319b2cc9f1799b68ff9c6680c1a7f93f701e` has the same tree. PRs #23–#27 were closed as incorporated without individual merges.
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

## Incorporated development-source baseline and outstanding product qualification

SF-08–SF-13 are integrated through protected PR #22. `docs/factory/work-orders/SF-R22.json` and `docs/factory/evidence/SF-R22.md` preserve the historical post-merge reconciliation.

As of 8 October 2026, **PR #28 is merged and PRs #23–#27 are administratively closed as incorporated**, with zero open PRs at the post-merge reconciliation baseline. The integrated development source includes exact externally pinned portable archive installation (#24), offline release planning (#25), synthetic fake-target deployment/recovery qualification (#26), offline health and work proposals (#27), and SF-19 cross-package fixture qualification (#28). Queue validation was independently observed at run 37840817630 and final `main` incorporation was separately confirmed. Historical work orders, candidate evidence, and original PR threads remain available as source provenance.

Important distinctions: a matching trust pin does not authenticate its issuer; SF-14 cannot authorize an actual release; SF-15 is in-memory simulated dispatch/recovery; SF-16 has no live telemetry or incident ownership. Production v1 readiness remains **blocked despite successful protected source incorporation**. SF-17/18 and SF-R10 budget/orchestration remain deferred. No target-project installation, external release, deployment, real recovery, or production activation is authorized.

See `docs/factory/SF19_QUALIFICATION.md` and `docs/factory/evidence/SF-19.md` for the historical candidate acceptance ladder and unresolved trust boundary; see `docs/factory/evidence/SF-R28.md` for factual post-merge SHA, provider checks and incorporation evidence.

## Production qualification programme (9 October 2026; PQ-00 candidate)

The later [protected PR #30 integration](https://github.com/spsoftwarefc/s-f/pull/30) supersedes PR #28 as the **starting `main` baseline**: `45a1d78197667efeedf5f2e60ca07f1ff070a6f6`, tree `c498695eb49d6ca4af2859fa2164a85881020837`. Its [merge-group evidence](https://github.com/spsoftwarefc/s-f/actions/runs/37845247779) does not alter the product-release blockers above.

Follow the new [PQ-00 through PQ-08 production qualification plan](SF_PRODUCTION_QUALIFICATION_PLAN.md) and [PQ-00 contract and threat/claim oracle](PQ00_CONTRACTS.md). PQ-00 is documentation/requirements freeze only; each subsequent numbered PQ package is a separate, authorized work order/PR with independent acceptance. The product remains a **development preview and not production-qualified** until genuine publisher/CI/grant/retained build, durable real-target recovery and live incident evidence are accepted for an explicit profile. No publication, target-project installation, deployment, SF-17/18 initiation or mandatory second reviewer is authorized by starting this programme. SF-R10 remains unmet overall.
