# s-f — Software Factory

s-f is a repository-local software production system for planning, implementing, verifying, reviewing, releasing and operating software changes.

Current state (8 October 2026): **SF-00–SF-13 are incorporated into `main` through protected PR #22**. The cumulative integration commit is `6c82b1230046650afcf28a61d7c8da7f8d157773`, tree `d95b8fc15c358992961e98d0adeb9f90dd07db09`. Linux, Windows and `sf07-acceptance` passed in the required `merge_group` run [37801503467](https://github.com/spsoftwarefc/s-f/actions/runs/37801503467). PRs #17–#21 were closed as incorporated, **not individually merged**.

The implementation is still a **development-preview factory**, not a public, production-qualified release. SF-13 distribution verification depends on an externally authenticated operator-controlled digest pin; publisher signatures, authenticated trust provisioning and **SF-06 installer enforcement of SF-13 locks** are not established. SF-14–SF-16 and SF-19 remain unimplemented; SF-17/18 are optional/deferred. A successful merge queue is source integration evidence, not installation provenance, deployment authority or release qualification.

Start with:
- `AGENTS.md` for repository operating boundaries.
- `docs/factory/WORKFLOW.md` for the lifecycle.
- `docs/factory/WORK_ORDER.md` for package checkpoints.
- `docs/factory/PROJECT.md` for this repository's adapter.
- `docs/factory/work-orders/SF-R22.json` and `docs/factory/evidence/SF-R22.md` for post-merge reconciliation.
- `docs/factory/CI_ENFORCEMENT.md` and `docs/factory/evidence/CI-16.md` for enforced checks and negative queue evidence.
- `docs/factory/SF07_QUALIFICATION.md` for historical portability qualification and limits.
- `docs/factory/SF06_LIFECYCLE.md` and `docs/factory/SF13_DISTRIBUTION.md` for lifecycle and distribution contracts.

For the integrated development-factory packages, consult `docs/factory/SF08_WORK.md` through `docs/factory/SF13_DISTRIBUTION.md` and corresponding `docs/factory/evidence/SF-08.md` through `SF-13.md`. Those historic package records retain their original candidate-stage limitations.
