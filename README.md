# s-f — Software Factory

s-f is a repository-local software production system for planning, implementing, verifying, reviewing, releasing and operating software changes.

Current state: **SF-07 portable installation foundation incorporated**, with enforced s-f GitHub Linux/Windows/`sf07-acceptance` checks and a **real successful merge-group integration** verified on merged PR #15. PR #16 additionally demonstrated **negative queue rejection** when a required job failed and another was skipped, then restored the original workflow. SF-08–SF-19 development lifecycle, generalized evidence verification, security, distribution, deployment and operations remain pending. This is **not** a production-qualified factory.

Start with:
- `AGENTS.md` for repository operating boundaries.
- `docs/factory/WORKFLOW.md` for the lifecycle.
- `docs/factory/WORK_ORDER.md` for package checkpoints.
- `docs/factory/PROJECT.md` for this repository's adapter.
- `docs/factory/work-orders/CI-16.md` for the current narrow closure, `docs/factory/CI_ENFORCEMENT.md` for the s-f-specific enforcement contract, and `docs/factory/evidence/CI-16.md` for the real negative merge-queue evidence.
- `docs/factory/SF07_QUALIFICATION.md` for the historical portability fixture matrix and its limits.
- `docs/factory/SF06_LIFECYCLE.md` for opt-in installation, upgrade, removal and recovery limits.
