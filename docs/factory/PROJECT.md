# Bot Trader factory adapter

Status: INFORMATIVE. Adapter document version: 1.3. Implements factory core (`docs/factory/WORKFLOW.md`) version: 1.2. This file routes to existing project authority; it is not another stage checklist.

## Purpose, boundaries and routing

Use `PLAN.md` for the project's purpose, standalone operating shape, stage sequence and canonical closure checklist. Resolve contract filenames/classifications through `docs/NORMATIVE_INVENTORY.json`. Preserve all domain rules in `AGENTS.md`; the factory does not replace them or introduce an LLM into runtime trading decisions.

| Need | Existing source |
| --- | --- |
| Work-package checkpoints, evidence record, completion stages and handoff | `docs/factory/WORK_ORDER.md` |
| Applying the checklist to bot implementation | `.agents/skills/bot-implementation/SKILL.md` |
| Domain acceptance references, domain review rules and stage packages | `docs/AGENT_EXECUTION_GUIDE.md` |
| Dependency discovery, symbol and section outlines, name search and source fingerprint | `.agents/skills/bot-context/SKILL.md`, `tools/context_map.py` |
| Review of accounting, recovery, grouping, incidents and evidence | `.agents/skills/bot-review/SKILL.md` |
| Requirement/evidence levels | `docs/REQUIREMENT_TRACEABILITY_v1.2.0.md` |
| Stage 1 current status | `docs/reviews/STAGE1_GATE_STATUS.json`, checked against `PLAN.md` |
| Operator contract decisions | `docs/reviews/CONTRACT_DECISIONS_PENDING.md` |
| Research-input qualification | `research/data/INPUT_QUALIFICATION_STATUS.json` |
| Venue procedures versus venue evidence | `docs/VENUE_QUALIFICATION_PROCEDURES_v1.md` and stage gates |
| Installed toolchain and executed commands | `.github/workflows/verify.yml`, `uv.lock`, `executor/package-lock.json` |

Do not treat historical counts in AGENTS.md or old completion reports as current status. Inspect the referenced ledgers at the task's actual source revision. This factory's readiness never changes a D/Q/S1 decision or venue qualification status.

## Instruction ownership map

Each workflow obligation has one owner; other files reference it rather than restating it. Several files are expected; conflicting definitions and copied instructions are the problem.

| Location | Owns | Avoids |
| --- | --- | --- |
| `AGENTS.md` | Project entry point, authority boundaries, mandatory routing, domain invariants | Repeating the implementation checklist |
| `SKILLS.md` | Skill selection and canonical skill locations | Independent workflow rules |
| `.agents/skills/bot-context/SKILL.md` | Dependency and impact discovery | A competing acceptance process |
| `.agents/skills/bot-implementation/SKILL.md` | How the builder applies project rules and the checklist | Copying checklist fields and schemas |
| `.agents/skills/bot-review/SKILL.md` | Review method and domain-specific questions | A second definition of completion |
| `docs/factory/WORKFLOW.md` | Reusable lifecycle and operating principles | Project-specific status and duplicated schemas |
| `docs/factory/WORK_ORDER.md` | Required checkpoints, structure criteria, proof, evidence, stages and handoff | A second project backlog |
| `docs/factory/PROJECT.md` (this file) | Bot-specific factory configuration, this ownership map, host routes and enforcement inventory | Repeated generic policy |
| `PLAN.md`, normative contracts and `docs/AGENT_EXECUTION_GUIDE.md` | Domain requirements, stage obligations and acceptance references | Competing factory procedures |
| `docs/factory/evidence/work-orders/`, `docs/factory/evidence/records/` | Package-specific declarations and results | New general rules |
| `CLAUDE.md` and any other host adapter | A pointer to `AGENTS.md` | Copied skill bodies or checklist content |

Host routes:
- **Claude Code:** reads `CLAUDE.md`, which imports `AGENTS.md`.
- **Hosts that read `AGENTS.md` directly:** enter there.
- **Any other host actually used for this repository:** gets a thin adapter that only points to `AGENTS.md`. Skill bodies live only under `.agents/skills/`.

The factory checker verifies required routing references, canonical skill locations and adapter thinness; a valid link does not prove the linked instruction is still correct.

User-level and host-global skills stay installed for other projects. When used here, they supplement the repository process within the instruction hierarchy and do not replace a work order, evidence or review. Automatic skill selection is changed only through a verified per-project mechanism for the host in use; without one, the routing above and AGENTS.md apply. Machine-specific findings about local checkouts and installed skills are recorded in `docs/factory/MIGRATION_REVIEW.md`, not here.

## Safe operating scope

Continue authorized contract, reference-model, synthetic, fake-venue and tooling development. Preserve the existing distinctions between specification, reference evidence, production implementation, venue qualification and live authorization. Ordinary CI has no exchange secrets. Development/review requests do not authorize trading, account funding, holdout access, credential changes or deployment.

Use the existing research acquisition budget and shared provenance ledger from AGENTS.md. A task branch or agent does not reset a cumulative cap. Development dependency downloads and market-data acquisition remain separately reported. Existing pause/resume and recovery authority rules remain in the normative contracts; this adapter grants no new controls.

Before building, apply the ancestry check in WORKFLOW.md §3 to any existing or host-created worktree; a host may create one from a stale or unrelated checkout. Before integrating dependent work, check dependency readiness and every workflow the candidate tree inherits: triggers, `permissions`, target branches and any job that writes or commits. A temporary or one-off workflow is removed, or separately justified and owned, before merge. Write permission is not itself a defect when a job is meant to write; an unowned or no-longer-needed write job is. Follow WORKFLOW.md §3 for stacked-branch integration. Current migration branches, blockers and closure evidence are recorded in `docs/factory/MIGRATION_REVIEW.md`, not in this adapter. Later work follows its own recorded source and authorization rather than copying a migration's branch or SHA.

## Proof and commands

Use existing acceptance rows and domain-specific proof rules. For backend changes, traces and independently derived outputs are primary; screenshots are required only when a visible interface is actually affected. A documentation-only factory change requires preservation, routing and integrity review plus applicable CI; it does not require invented trading simulations or new behavioral tests mirroring prose.

The current verify workflow runs locked Python/TypeScript installation, pytest, contract crosscheck, manifest verification, fixture sync, context-map checks, Stage 1 consistency, venue procedure completeness, incident resolution, proposal/outbox recovery, pending-decision evidence, research-input evidence and hygiene. Preserve all these gates. Consult the workflow for the full commands rather than maintaining another copied command list.

At the migration source, CI requests Python 3.12 through uv 0.12.0, Node 20.19.6 and action major tags; this is a source observation, not a claim that every dependency or runner is immutable or that the future production runtime has been qualified. Review deployment-toolchain consistency in the production implementation stage. Since RT-1 (2026-09-21) CI and the executor's `engines` field pin Node 24.21.0 LTS, the operator's choice so the Stage 3 ledger can use built-in `node:sqlite`; Node 20 is end of life.

## Enforcement inventory and next factory packages

| Package/control | Status at migration | Acceptance needed |
| --- | --- | --- |
| PF-1 factory workflow, host routing, preservation and work-order template | Implemented as documentation in this change; review/CI disposition belongs in its PR | Existing rules retained; links/authority consistent; integrity and applicable CI pass |
| Existing contract/fixture/domain consistency gates | Existing executable CI | Preserve gate behavior and exact-revision evidence; passing consistency is not Stage 1 freeze |
| Existing hygiene scan | Existing narrow pattern scan | Do not describe it as comprehensive secret scanning or vulnerability analysis |
| PF-2 instruction/evidence automation | Implemented as the verify step "Factory routing, preservation and evidence checks" (`tools/check_factory_evidence.py`, control lists, work orders and records in `docs/factory/evidence/`). Corrections are in PF-2.1 through PF-2.4; PF-2.4 binds new work orders to computed project-map impact and invariant/test review without adding a second disposition ledger | Behavior per `docs/factory/PF2_WORK_ORDER.md` 1.5 and the authoritative checklist `docs/factory/WORK_ORDER.md` 1.5: pre-implementation work orders, per-obligation before/after results, structure review, candidate/acceptance stages, resume checkpoint. Limits: removal is visible and must be recorded, not prevented; branch protection is unavailable on the current plan; a present heading does not prove preserved meaning; a matching execution fingerprint does not prove equivalent enforcement; run facts and approvals are attested, not verified; the checker validates form and binding, not the truth of evidence |
| PG-1 project map | Implemented as `docs/map/PROJECT_MAP.json` and `tools/project_map.py`, checked by the verify step "Project map consistency" | Map data declares only objectives, criteria, stages, gate predicates, work, evidence bindings, components, interfaces and the CTJ boundary; packages, requirements and all state are derived from work orders, records, `PLAN.md`, the traceability matrix and the Stage 1 and research-input ledgers. Unknown or untracked state never satisfies a gate. The rendered page (`python tools/project_map.py --render <file>`) is generated per revision and not committed. Limits: evidence staleness follows declared `dependsOn` inputs, not a full dependency analysis; the Stage 1A gate approximates per-assumption evidence with the item 4b ledger value; the map reports state and grants no authority |
| PF-3 security and supply-chain automation | Planned, not installed | Select compatible scans; verified action SHA pinning, dependency/license review and credential exclusions; demonstrate injected failures; define update ownership and explicit exception handling |
| PF-4 controlled release and continuous operation | Planned for the applicable production stages | Artifact identity, release permissions, restore/reconciliation exercise, monitoring/incident ownership and cadence; no trading activation without existing gates and operator authorization |
| Hosted reviewer or extra human reviewer | Not a required dependency | Use existing self-review and source/evidence review; disclose independence limits; third-party service adoption is a separate integration decision |
| Automatic factory copying for future repositories | Not installed | Run WORKFLOW.md bootstrap explicitly during repository creation; parameterize and validate every project adapter |

PF packages describe factory adoption work, not a replacement bot backlog. Add any implementation package to the existing planning process before executing it. Do not create a second status JSON that can contradict Stage 1 or research status. No scheduled monitoring, external reviewer integration or release job is activated by this documentation change.

## Release and operational handoff

Before production activation, the operator must identify the release/incident owner, dependency review cadence, health thresholds and evidence retention in the relevant deployment/runbook work package. The operator owns policy acceptance and live authorization; agents may prepare changes and evidence within existing authorization. Until the production package supplies these controls, describe them as unimplemented.

A code rollback cannot undo an exchange order. Any operational rollback or restore must preserve the existing journal, single-authority, account reconciliation and recovery rules. This requirement is why the factory's release phase remains subordinate to the bot's domain contracts.


### PF-2.4 semantic-impact binding

New work packages declare expected project-map nodes, interfaces, evidence bindings and affected invariants before implementation. At candidate/acceptance validation the checker derives the actual map impact from the real package diff using `tools/project_map.py`; authors cannot self-attest the actual side. Missing declaration coverage is pending on candidate branches and fails acceptance until the work order is amended. The evidence record reviews invariant tests, unexpected impact and explicitly unaffected boundaries. Limits are deliberate: the map is coarse (for example, `executor/` is currently one component), `context_map.py` is advisory, and neither establishes semantic completeness inside a component. CI tiering and finer executor decomposition are separate future packages, not PF-2.4.
