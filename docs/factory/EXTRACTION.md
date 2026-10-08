# Factory extraction provenance

Source: [ctj-bot/ctj-spot-bot](https://github.com/ctj-bot/ctj-spot-bot) at commit `ce2c0adff0944f35aff1575ddf6b6252c84424c6` (source main inspected 2026-10-08).

Destination: `spsoftwarefc/s-f`; baseline branch `extract/portable-factory-core`.

Imported: the production-cycle documentation and work-order checklist with minimal routing updates; original structure and substance are retained.

Intentionally excluded from this baseline: `docs/factory/PROJECT.md` from the bot (replaced with this project's adapter), `docs/factory/MIGRATION_REVIEW.md`, `docs/factory/PF2_WORK_ORDER.md` (historical bot migration/work packages), `docs/factory/evidence/` (bot work orders and results), `tools/check_factory_evidence.py` and its tests (hard-coded bot coupling), `.github/workflows/verify.yml` (bot build/venue/research jobs), and bot-specific agent skills. These are *candidates* for future refactoring rather than drop-in portable controls.

No files were deleted or modified in the source repository. No source branch or PR was altered. This extraction does not establish enforcement or test pass results.
