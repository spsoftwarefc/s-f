# s-f factory adapter

Status: INITIAL EXTRACTION — documentation baseline, not an operational enforcement claim.

## Scope

This repository holds portable factory process standards to be reused by projects through explicit, reviewed adoption. It has no authority to alter ctj-bot/ctj-spot-bot, accordquill/accordquill or other consumers.

Canonical process: [WORKFLOW.md](WORKFLOW.md). Canonical work-package checklist: [WORK_ORDER.md](WORK_ORDER.md). Entry point: [../../AGENTS.md](../../AGENTS.md).

## Project configuration

No application runtime or project-specific build/test commands are defined in this repository. Consumer repositories must supply architecture, contracts, acceptance criteria, work-order/evidence storage and gate enforcement. Source-specific references in extracted documents are historical context, not ready-to-run integrations.

## Enforcement status

- Documentation and work-order process: imported for review.
- Python evidence checker and tests: NOT PORTED (deeply tied to bot paths, records and CI).
- GitHub Actions verification: NOT CONFIGURED. Do not claim CI verification.
- Bot historical evidence, trading strategies, exchange access and production deployment: EXCLUDED.
- New changes: use reviewable PRs. CI design and preservation tests are separate follow-up work.

See [EXTRACTION.md](EXTRACTION.md) for provenance and exclusions.
