# s-f — Software Factory

s-f is a repository-local software production system for planning, implementing, verifying, reviewing, releasing and operating software changes.

Current state (8 October 2026): **SF-00–SF-07 foundation is merged** and GitHub required Linux/Windows/acceptance checks plus a successful and negative merge-queue probe were verified. **SF-08 through SF-13 are implemented as an open, unmerged PR #17–#22 stack**, with PR #22 the intended cumulative integration to `main`. Installation-planning and verification remain development-preview capabilities; SF-13 uses an out-of-band approved digest pin and explicitly **does not verify publisher signatures or enforce lock use in SF-06 installation**. **SF-14–SF-16 deployment and operations and SF-19 v1 qualification are not implemented.** A green PR is not merge-queue, deployment or production-release authorization.

Start with:
- `AGENTS.md` for repository operating boundaries.
- `docs/factory/WORKFLOW.md` for the lifecycle.
- `docs/factory/WORK_ORDER.md` for package checkpoints.
- `docs/factory/PROJECT.md` for this repository's adapter.
- `docs/factory/work-orders/SF-13.json` for the active package declaration, `docs/factory/CI_ENFORCEMENT.md` for the s-f-specific enforcement contract, and `docs/factory/evidence/CI-16.md` for the real negative merge-queue evidence.
- `docs/factory/SF07_QUALIFICATION.md` for the historical portability fixture matrix and its limits.
- `docs/factory/SF06_LIFECYCLE.md` for opt-in installation, upgrade, removal and recovery limits.

For the open development-factory stack, consult `docs/factory/SF08_WORK.md` through `SF13_DISTRIBUTION.md` and the matching `docs/factory/evidence/SF-08.md` through `SF-13.md`. The authenticated-trust-pin origin is an external operator prerequisite, not established by bundle self-hashes.
