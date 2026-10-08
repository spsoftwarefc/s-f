# Factory extraction provenance and reconciliation register

Source repository: `ctj-bot/ctj-spot-bot`
Source commit: `ce2c0adff0944f35aff1575ddf6b6252c84424c6`
Destination: `spsoftwarefc/s-f`
Initial extraction head: `9d2d0d237fe7d94559e4baed62103ba38d0a470d`
Reconciliation package: SF-00

The source repository is read-only provenance for this extraction. No source-bot file, branch, PR, credential, runtime or deployment resource is modified by s-f work.

## Imported-file classification

| Imported material | SF-00 disposition |
| --- | --- |
| `docs/factory/WORKFLOW.md` | Keep as portable source, then refine in later packages. |
| `docs/factory/WORK_ORDER.md` | Keep as portable source, then formalize with schemas in later packages. |
| `AGENTS.md`, `CLAUDE.md`, `SKILLS.md` | Adapt to s-f-only routing. |
| `.agents/skills/bot-*` | Temporary source candidates; replaced by generic factory skills in the SF-00 stack. |
| `docs/factory/PROJECT.md` | Replace bot adapter with the s-f repository adapter. |
| `docs/factory/MIGRATION_REVIEW.md` | Historical bot migration record; remove from the portable baseline. |
| `docs/factory/PF2_WORK_ORDER.md` | Historical bot package record; remove from the portable baseline. |
| `docs/factory/evidence/*.json` imported from the bot | Historical/source-coupled control state; remove from the portable baseline. |
| `tools/context_map.py` | Candidate reusable mechanic; retain only after portable tests are self-contained. |
| `tools/test_context_map.py` | Adapt by replacing repository-coupled assertions with synthetic fixtures. |
| `tools/check_factory_evidence.py` and `tools/test_factory_evidence.py` | Source candidate only during SF-00; either decouple or remove before baseline acceptance. No enforcement claim while coupled to absent bot contracts. |
| Bot `.github/workflows/verify.yml` | Not imported. s-f installs no hosted workflow in SF-00. |

## Baseline rule

Historical bot facts may remain only in provenance text that is explicitly labelled historical. They must not appear as current s-f authority, readiness, release status, routing, command requirements or evidence.

The combined SF-00 stack is not accepted until PR #4 closes the remaining skill/tooling coupling. No hosted CI success is claimed for this package.
