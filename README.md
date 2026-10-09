# s-f — Software Factory

s-f is a repository-local software production system intended to accompany projects from planning and controlled implementation through verification, release planning and operations, while respecting target-project authority.

**Prior protected integration:** SF-00–SF-13 were incorporated via [PR #22](https://github.com/spsoftwarefc/s-f/pull/22) at `6c82b1230046650afcf28a61d7c8da7f8d157773` (tree `d95b8fc15c358992961e98d0adeb9f90dd07db09`). [Merge-group run 37801503467](https://github.com/spsoftwarefc/s-f/actions/runs/37801503467) passed Linux, Windows and acceptance. PRs #17–#21 were closed as incorporated, not separately merged.

**Current protected integration (8 October 2026):** [PR #28](https://github.com/spsoftwarefc/s-f/pull/28) incorporated the full development stack through SF-19 into `main` as `ad573a2d900d4fef8211455ab9512e4a8003ac17` (tree `c3f07bc882770abb795af7fe14bc414552cb2fe3`). [Merge-group run 37840817630](https://github.com/spsoftwarefc/s-f/actions/runs/37840817630) passed native Linux, Windows and `sf07-acceptance` required checks before GitHub's protected squash merge at 2026-10-08 20:40:27 UTC. PRs #23–#27 are closed **as incorporated**, not individually merged. The cumulative source includes SF-13I verified source-byte installation, SF-14 offline release planning, SF-15 fake-target recovery, SF-16 offline operational feedback and SF-19 cross-package synthetic qualification. This is **development-source integration**, not public or production release acceptance.

**Production/public release is not qualified.** External trust pin matching is not publisher signing or authenticated pin issuance. SF-14's approval is operator-provided, SF-15 uses an in-memory fake target without live dispatch/durable recovery, and SF-16 consumes offline unauthenticated observations with no real alert/incident system. SF-17/18 optional orchestration/budget work remains deferred; SF-R10 is unmet. Successful PR-stage and merge-group tests can qualify development-source integration only—not a public production v1 release, real deployment, target-project installation, or release authority.

Start with `AGENTS.md`, `docs/factory/WORKFLOW.md`, `docs/factory/WORK_ORDER.md`, `docs/factory/PROJECT.md`, and `docs/product/REQUIREMENTS.md`. See `docs/factory/SF13_DISTRIBUTION.md`, `docs/factory/SF06_LIFECYCLE.md`, `docs/factory/SF14_RELEASE_PLAN.md`, `docs/factory/SF15_DEPLOYMENT_RECOVERY.md`, `docs/factory/SF16_OPERATIONS.md`, and `docs/factory/SF19_QUALIFICATION.md` for exact capability and trust boundaries. Per-package work orders and evidence are in `docs/factory/work-orders/` and `docs/factory/evidence/`. Post-merge source-bound reconciliation is in `docs/factory/evidence/SF-R28.md`; the original SF-19 candidate evidence remains a historical pre-integration record.

**Resource and authority rules:** one work order before implementation, one stacked PR at a time, no redundant GitHub Actions usage, no mandatory reviewer request, no bypass of protected merge queue, no changes to unrelated projects, and no merge/deployment outside the active authorization boundary.

## Production qualification — PQ-00 to PQ-08 (9 October 2026)

Following [protected PR #30](https://github.com/spsoftwarefc/s-f/pull/30), the programme baseline is `main` at `45a1d78197667efeedf5f2e60ca07f1ff070a6f6`. Source test/merge success **does not** qualify public distribution or production deployment. The production-qualification programme starts with **PQ-00 requirements/authority contract freeze**, followed by authenticated publisher and independent CI/release authority, controlled artifacts, SQLite durable recovery, a real disposable Linux reference target, live operations, scoped qualification and separately authorized publication/adopter pilot.

See the [production qualification implementation plan](docs/factory/SF_PRODUCTION_QUALIFICATION_PLAN.md), [PQ-00 boundary contracts](docs/factory/PQ00_CONTRACTS.md), and the active [PQ-00 work order](docs/factory/work-orders/PQ-00.json). PQ-00 only prepares the contracts; no signed public release, credential, installation, deployment or new authorization is asserted. SF-17/18 remain deferred and SF-R10 remains unmet overall.

## PQ-01B–PQ-06 partial source incorporated; PQ-07A next

[PR #38](https://github.com/spsoftwarefc/s-f/pull/38) protected squash-merged the six partial-source packages on 9 October 2026 as `766509f380b901a8672d7ee7b2137ef28a234685`, following successful [merge-group run 37897557665](https://github.com/spsoftwarefc/s-f/actions/runs/37897557665). Lower PRs #33–#37 were closed as incorporated. All existing publisher, release, deployment and operational **production** qualification limits remain in force; passing 376 tests/platform and protected CI does not authenticate external provenance or grant deployment authority.

PQ-07A adds a read-only source/evidence dossier gap assessor for the limited disposable single-host Linux test profile. It explicitly cannot accept self-asserted trust evidence. Real PQ-07 external qualification and PQ-08 publication/adopter pilot are not authorized or complete. See the production qualification plan and PQ-07A work order for exact scope and exclusions; SF-R10 remains unmet overall.

## PQ-07A–F source-readiness work (PRs #39–#44)

Following the source-only protected merge of PQ-01B–PQ-06, PQ-07 now has six independently bounded **source-candidate** packages (dossier validation, operator-policy digests, local process-death recovery observations, exact retained-build input byte comparison, source-bound local evidence registry and cross-package no-go preflight). Their accepted local checks do **not** mean a production-ready publisher or authenticated deployment; the cross-package preflight intentionally always blocks publication, adopter pilots and `productionQualified` until separate genuine external qualification.

[PR #44](https://github.com/spsoftwarefc/s-f/pull/44) subsequently completed the protected source-only integration on 9 October 2026 at `5d042208a148f9b75a429b11c8fe63f1ccef65d0`. PRs #39–#43 were closed as incorporated, not individually merged. The required Linux/Windows/acceptance and separate protected merge-group controls stay in force. **Production qualification and PQ-08 publication/adopter pilot are still blocked.**

## PQ-07G–L source work — protected merge PR #50 completed

PRs [#45](https://github.com/spsoftwarefc/s-f/pull/45)–[#49](https://github.com/spsoftwarefc/s-f/pull/49) add offline operator-pinned raw campaign evidence intake, bounded read-only CLI, cross-evidence preflight, external custody-decision gap reporting and adversarial false-green tests. [PR #50](https://github.com/spsoftwarefc/s-f/pull/50) is the sole cumulative protected integration checkpoint, not a public release. The lower draft PRs must not be individually merged.

Even complete local proof bytes and fully declared owner names are *not* authenticated producer, CI, grant, immutable storage, live target or operational evidence. The independently authenticated PQ-07 live campaign remains unperformed. PQ-08 requires separate independent publication and adopter authorization. SF-R10 remains unmet overall. See the [production qualification plan](docs/factory/SF_PRODUCTION_QUALIFICATION_PLAN.md) and new work orders PQ-07G–L.


## PQ-07M–R production qualification preparation (PRs #51–#56)

[PR #50](https://github.com/spsoftwarefc/s-f/pull/50) integrated PQ-07G–L source via protected queue as `0a59eb0078826530493db0c2a0211470d9368a8d` on 9 October 2026; [merge-group 37908722988](https://github.com/spsoftwarefc/s-f/actions/runs/37908722988) passed. The next merge checkpoint is PR #56, with separate work orders and one active stacked PR at a time. See [external activation prerequisite contract](docs/factory/PQ07_EXTERNAL_ACTIVATION.md). The publisher/CI/grant/artifact/target/operator proof is **not** independently accepted, and no live qualification, public publication or adopter pilot has been authorized. `productionQualified=false`; SF-R10 remains unmet overall.


## PQ-07M–R source qualification implementation — cumulative PR #56

PRs [#51](https://github.com/spsoftwarefc/s-f/pull/51)–[#55](https://github.com/spsoftwarefc/s-f/pull/55) form a sequential, work-order-first **source-only** stack: externally custodied activation contract, manual-only preview provenance workflow, operator-pinned provider read, retained-byte/publisher join, and isolated local process-death recovery plus a separate live runbook. Only [PR #56](https://github.com/spsoftwarefc/s-f/pull/56) is intended for protected `main` merge-queue consideration. The new preview workflow has **not been manually dispatched** and cannot be triggered by PR or push events.

These are testable qualification-preparation mechanisms, not authenticated live production acceptance. Independent actual release signer, protected grant/revocation, immutable external artifact, remote target and authenticated incidents remain mandatory and unavailable. PQ-07 live remains **BLOCKED**, PQ-08 remains **NOT STARTED**, SF-R10 **UNMET overall**. See [external activation contract](docs/factory/PQ07_EXTERNAL_ACTIVATION.md) and [reference runbook](docs/factory/PQ07_REFERENCE_RUNBOOK.md).

## PQ-07S live qualification handoff — next protected checkpoint PR #62

[PR #56](https://github.com/spsoftwarefc/s-f/pull/56) is protected squash-merged as `a462d5306c731341c4c915797693edb8e1c71615` on 9 October 2026 (10:03:31 UTC). The separate [merge-group run 37914839522](https://github.com/spsoftwarefc/s-f/actions/runs/37914839522) succeeded for that integration SHA. This accepts PQ-07M–R **source preparation**, not a live release or target qualification.

The next merge checkpoint is **PR #62**, after sequential bounded work orders/PRs #57–61. [PQ-07S live campaign handoff](docs/factory/PQ07_LIVE_CAMPAIGN_HANDOFF.md) records independently owned operator activation prerequisites, explicit NO-GO states and intended work sequencing. Only PR #62 is eligible for the next protected integration; earlier PRs are source-only dependent drafts. No signing dispatch, remote deployment, publication, adopter pilot or production VPS use is authorized by this plan. Real PQ-07 **NO-GO**; PQ-08 **NOT STARTED**; SF-R10 overall **UNMET**.

## PQ-07S–X source-only integration — protected PR #62

Draft PRs [#57](https://github.com/spsoftwarefc/s-f/pull/57)–[#61](https://github.com/spsoftwarefc/s-f/pull/61) prepare read-only campaign identity, retained publisher/provider evidence joins, disposable Linux reference-target declarations and local negative/incident case review, with strict **NO-GO** outputs and adversarial tests. The *only* next intended merge into protected `main` is cumulative [PR #62](https://github.com/spsoftwarefc/s-f/pull/62). It requires the exact-head Linux, Windows and `sf07-acceptance` checks plus the separate protected SQUASH `merge_group` before integration. Lower draft PRs are **not separately merged**.

Source validation does not establish real publisher key-policy custody, immutable externally held artifact, release grant/revocation, authenticated live remote target/health/incident evidence or independent profile approval. **PQ-07 live remains NO-GO, PQ-08 publication/pilot NOT STARTED, SF-R10 overall UNMET.** See [campaign handoff](docs/factory/PQ07_LIVE_CAMPAIGN_HANDOFF.md) and [qualification plan](docs/factory/SF_PRODUCTION_QUALIFICATION_PLAN.md).
