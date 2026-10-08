# AGENTS.md — s-f

This repository hosts the reusable Software Factory extracted from ctj-bot/ctj-spot-bot. It is not the trading bot and grants no authority over other repositories.

Read docs/factory/WORKFLOW.md (process), docs/factory/WORK_ORDER.md (work-package checkpoints), and docs/factory/PROJECT.md (this repository's adapter).

Before implementation, record a bounded work order and source/base revision. Use a task branch; one PR at a time. Collect source-bound before/after or behavioral proof, review actual changes, and report checks precisely. Do not merge or deploy merely because implementation or advisory review is complete. Preserve other work and minimize redundant GitHub Actions runs.

The original bot's trading contracts, credential rules, historical evidence, and stage gates are not imported. No checker or CI enforcement is claimed until specifically implemented and validated.
