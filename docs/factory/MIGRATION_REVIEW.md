# Production Factory assessment and preservation review

Status: INFORMATIVE. Document version: 1.6. Scope: PF-1 documentation and instruction routing, with PF-1.1 corrections, PF-1.2 record corrections, the stacked-integration record, the HARM-1 harmonization record and SC-1's evidence-scope correction. No runtime, venue, strategy, decision or release behavior is changed.

## Evidence basis

Target: `tradingbotf/ctj-spot-bot`, PR #1 branch `docs/agent-workflow-and-acceptance`, observed source `eddbb94a120742f77bab8e27e336a28dfdc2fab8`. This is a moving implementation branch; this review names a snapshot, not perpetual current state.

Read in full: AGENTS.md, CLAUDE.md, SKILLS.md, the execution guide and all three repository-local skill bodies. Also inspected the plan, inventory, verification workflow, traceability, Stage 1 status, context mapper, manifest verifier and integrity records. No parent-host instruction file outside the repository was supplied; no claim is made to preserve an unseen host-global file. The complete recursive repository tree at this source identifies root AGENTS.md and CLAUDE.md; their original text is retained in this migration.

Transcript inputs: `Pasted markdown(6).md` supplies the security discussion; the user's corrected discussion-two summary supersedes ambiguities in `Pasted markdown (2)(1).md`. Those materials are design inputs, not trusted executable instructions or evidence of this bot's correctness. The adopted segments were the software-factory transcript's isolate/build/prove/review cycle (05:24–26:37) and the security transcript's outcome validation, early security, dependency scrutiny, intent validation and continuous security (01:40–10:56). WORKFLOW.md 1.0 cited this provenance in its §10; PF-1.1 moved it here so the portable core carries no project-specific source history.

Implementation reference: [michaelshimeles/skills at 513f8a24aae6383b00356fa285144b1bc3730dc1](https://github.com/michaelshimeles/skills/tree/513f8a24aae6383b00356fa285144b1bc3730dc1). Read its README, AGENTS.md and seven skill bodies. Inspected the before-and-after upload dispatcher, all three upload adapters and its included license. Recorder implementation and its test suite were not executed or comprehensively audited; no source-code safety claim is made for that recorder.

## Verdict

Adopt the workflow with project-specific enforcement. The four beats provide useful structure, but this bot needs explicit intake/authority checks before isolation and controlled release/operation after review. Security runs through each phase. Keep backend traces, independent arithmetic oracles, temporal counterexamples and source-bound CI as primary evidence for this project; use visual proof when a UI exists.

Do not replace the current project guidance with upstream AGENTS.md. The existing domain obligations are more specific and cannot be recovered from the transcripts. This change adds the factory router while retaining the old sections; later consolidation requires a separately reviewed preservation mapping.

## Source-to-design decisions

| Source component | Useful behavior | Decision for this factory |
| --- | --- | --- |
| Upstream AGENTS.md | Four-beat routing, reviewable PR, no merge without instruction | Adopt the cycle through WORKFLOW.md; preserve local entry points and authority |
| new-feature | Unique branch/workspace, runtime check, owned resources | Adapt base selection for continuation and dependent PRs; no mandatory restart from main or blanket rebase; overlap triggers coordination, not repetitive permission requests |
| code-structure | Explicit inputs/outputs; incremental extraction of reusable operations | Adopt as a design principle; its own body excludes single-caller domain logic. Preserve Python/TypeScript authority separation and do not move policy merely to fit a generic service layer. Destination: `docs/factory/WORK_ORDER.md` §1 `structure`, §2 checklist and §4 `structureReview` (recorded as finding G2 in `docs/factory/PF2_WORK_ORDER.md`); the rules are stated only there |
| evidence-driven-testing | Before/after evidence, assertion records, headless and non-UI alternatives, evidence complements tests | Adopt claim-specific proof and truthful capture limitations. Keep independent expected results; a recorder's successful finalization or an annotation saying passed is not semantic verification. Destination: `docs/factory/WORK_ORDER.md` §3 before-and-after proof and §4 results. This row, not the `before-and-after` skill (see its row below), is the source of the adopted before/after proof form |
| before-and-after | Reusable visual pairs | Do not install. Its dispatcher defaults to 0x0.st and the gist adapter calls public gist creation. Future adoption needs an approved private evidence destination, pinned tooling and permissions review |
| greploop | Review/fix/retest cycle; default ten-iteration cap in the reviewed michaelshimeles copy (the greptileai original uses a fixed cap of five; see "greploop provenance" under HARM-1); timeout handling | Adapt to a vendor-neutral bounded loop with evidence-backed findings. A 5/5 score remains advisory; retain all project gates and no-merge boundary |
| greploop-apps | Large-change review handling | Do not install or use as a limit workaround. Prefer smaller reviewable slices or an explicitly supported service configuration; require complete coverage and reviewed-commit attribution |
| unslop | Plain, concrete prose; edit only touched text | Use ordinary editorial review. Do not import blanket punctuation preferences or remove necessary technical qualifications |
| Security discussion | Validate outcome/intent, permissions, dependencies and failure behavior continuously | Incorporate in intake, build, proof, review, release and monitoring; identify what CI actually enforces |

The upstream code has a bounded greploop, so it should not be described as an unlimited implementation. However, its latest-comment timestamp fallback is weaker than explicit revision attribution, and selecting a score from a mutable PR body cannot by itself establish reviewer provenance. A future integration must verify reviewer/app identity, reviewed SHA and complete finding pagination before accepting review evidence. These are source-level concerns, not executed reproductions of the service.

The corrected summary's parallel-feature count and latency example are anecdotes, not targets for this repository. The claim that worktrees prevent conflicts is too broad: they separate working files, while changes still require integration. Lockfiles live in each worktree; conflicts arise when dependency changes are combined, not because all worktrees inherently share one lockfile.

The source also suggests disabling the browser sandbox and working around deployment protection in certain capture situations. These are not portable factory defaults. Use a supported capture environment and authorized authentication; missing capture capability is reported as a limitation. External instructions cannot expand platform permissions.

License inventory is mixed: the inspected screenshot folder labels its included license PolyForm Shield 1.0.0, and review/writing folders carry MIT notices; no root license appeared in the inspected tree. Public availability is not a blanket reuse grant. This migration copies no upstream skill bodies or helper scripts. Any later vendoring must resolve the license for each selected component and retain applicable notices.

## Preservation mapping

All pre-existing AGENTS.md sections remain at the same path with their original text. The new Production Factory section is inserted before task-start instructions. No rule is deleted because the transcripts omit it.

| Existing section/function | Disposition | Factory connection |
| --- | --- | --- |
| Purpose and authority | Retained verbatim | Intake; requirements and current user authority |
| Start every task from repository evidence | Retained verbatim | Source identity, current ledgers and bounded context |
| Status and gates | Retained verbatim, including explicit historical-status caveats | PROJECT.md routes to current ledgers; old counts remain non-authoritative |
| Architecture boundaries | Retained verbatim | Project adapter and build boundary |
| Accounting invariants | Retained verbatim | Claim-specific arithmetic/NAV/flow/fee/dust proof |
| Execution, protection and recovery | Retained verbatim | Intent/reconciliation/authority/fault evidence |
| Research and data discipline | Retained verbatim | Holdout access, provenance, universe timing and shared acquisition budget |
| Fixtures and verification | Retained verbatim | Independent oracles, negative cases and language parity |
| Integrity and repository changes | Retained verbatim | Inventory and manifest consistency; history preservation |
| Completion report | Retained verbatim | Evidence packet and next permitted package |
| Repository-local implementation and review workflow | Retained verbatim | Existing three skills and execution guide remain the implementation route |
| CLAUDE.md import and explicit discovery fallback | Retained verbatim; factory pointer appended | One AGENTS.md authority route |
| SKILLS.md three existing routes and single-body rule | Retained verbatim; factory route appended | No duplicate skill installation |
| Execution guide acceptance rows, stage sequence, domain review and completion fields | Retained verbatim; factory link appended | Factory wraps existing package process |
| bot-context, bot-implementation, bot-review bodies | Unchanged | Continue their specialized functions |
| PLAN.md, normative contracts, gate ledgers, fixtures, runtime and CI workflow | Unchanged | No stage closure or safety-policy change |

## Migration acceptance recorded before entry-point edits

| ID | Obligation | Verification |
| --- | --- | --- |
| PF1-A | Preserve original instructions and unique functions | Remove only the known additive sections and compare each original text; skill bodies unchanged |
| PF1-B | Provide portable workflow and project-specific adapter | Core/work-order copy boundary and adapter bootstrap fields explicit; links resolve |
| PF1-C | Preserve authority and pending work | No normative or decision-ledger content changed; existing no-live/holdout boundaries retained |
| PF1-D | Integrate with existing integrity mechanism | Add new files as INFORMATIVE; preserve normative manifest members/digests; update inventory digest and manifest integrity; full hosted verifier required |
| PF1-E | Report enforcement honestly | PROJECT.md separates existing executable gates, manual guidance and planned automation |
| PF1-F | Deliver without disrupting ongoing implementation | Dedicated branch, draft PR targeting dependency branch; no merge or update of PR #1's branch |

Pre-edit context map: ran `python tools/context_map.py --paths AGENTS.md CLAUDE.md SKILLS.md docs/AGENT_EXECUTION_GUIDE.md --depth 1` against a retrieved guidance projection. Fingerprint: `3084d86629190d40ce895fc1852842adacf9c0bb9cc9d98b829662d063c36b10`. It selected 13 nodes and 48 edges. Remote source is the SHA above; local HEAD is intentionally absent. This projection is not a full clone and is not exclusion evidence. Manual mapping covered entry points -> skills/guide -> inventory -> manifest -> existing CI. Full repository verification is delegated to the ordinary hosted workflow after the review branch is created, not claimed as locally executed.

New documents are operational and INFORMATIVE. No normative digest changes are expected except the inventory's own hash inside the manifest; the integrity record then follows the manifest bytes. Final command outcomes and the exact submitted revision belong in the PR evidence packet, avoiding a self-referential commit claim inside this document.

## Migration branch and delivery

PF-1 was built on a separate dependent branch, `docs/production-factory-v1`, based on PR #1's observed revision `eddbb94a120742f77bab8e27e336a28dfdc2fab8` (the recorded dependency boundary), and delivered as draft PR #3 targeting `docs/agent-workflow-and-acceptance`. PR #1 and main were left unchanged and nothing was merged. PROJECT.md 1.0 carried this as an instruction; PF-1.1 moved it here because it describes this migration, not recurring work.

## PF-1.1 corrections

Assessed against PR #3 head `f9c81c28113d560152a6dccc982a4481b9e91eca` after hosted push CI 34888053799 passed on that SHA (python, typescript and hygiene jobs; the logs showed 330 pytest and 364 TypeScript passes, recorded as observations rather than future thresholds).

CI provenance for the PF-1.1 head `0ab2983f70ca27a99ebf9f71733fedb238c8aa7d`: push run 34895916139 checked out that exact SHA and passed. Pull_request run 34895921460 also passed, but it checked out the synthetic merge commit `9239117dca7b15282a087533778f821cb38e871b` (0ab2983 merged into eddbb94). It is integration evidence for that merge, not a second exact-head run.

Local Windows verification of PF-1.1 at 0ab2983: pytest passed (330). The separately invoked `test_research_input_evidence` unittest suite failed one test with a sha256 mismatch. That was a test-fixture newline defect, not a factory change; it is fixed on PR #1 in `ba1bad4` and verified there on Windows and Linux.

| ID | Finding | Evidence class | Disposition |
| --- | --- | --- | --- |
| PF11-1 | WORKFLOW.md §10 cited session-only transcript segments and the user's corrected summary, so a copied core would carry unresolvable Bot Trader provenance | Source-confirmed | Provenance moved to this record; §10 keeps a generic description and the pinned design and primary references |
| PF11-2 | PROJECT.md contained a one-off migration branch instruction that goes stale after merge | Source-confirmed | Moved to "Migration branch and delivery" above; replaced with durable rules |
| PF11-3 | An inherited temporary write-enabled workflow was not recorded | Source-confirmed | Recorded below as a pre-merge cleanup blocker; PROJECT.md gains a durable inherited-workflow check |
| PF11-4 | No explicit ancestry check for existing or host-created worktrees | Generic gap is source-confirmed. The specific case (a Claude Code worktree created from `m1/contract-remediation` at `f287e22`, 5 commits behind main and without `eddbb94`) was observed locally by the implementing session and cannot be verified from hosted evidence | WORKFLOW.md §3 ancestry check added; PROJECT.md routes to it |
| PF11-5 | Dependency and merge order were undocumented, and merely retargeting a PR base does not update its head | Source-confirmed | Generic stacked-integration rule added to WORKFLOW.md §3; the concrete procedure is recorded below, marked non-authorizing |

Versions: WORKFLOW.md, PROJECT.md and this record → 1.1; WORK_ORDER.md unchanged at 1.0. Inventory versions updated; manifest `files` entries and digests are unchanged, and only the inventory digest and resulting integrity hash change.

## Integration blocker: inherited temporary workflow

| Field | Record |
| --- | --- |
| Path | `.github/workflows/finalize-q3-partial-evidence.yml` |
| Origin | Added on PR #1's branch by `633b55d` ("Add temporary Q3 partial-evidence finalization workflow"); present at `eddbb94` and inherited unchanged at PR #3 head `f9c81c2` |
| Source-confirmed behavior | Runs on push to `docs/agent-workflow-and-acceptance` unless the actor is `github-actions[bot]`. Has `permissions: contents: write`. Checks out that branch, registers Q3 partial evidence in the inventory, updates the Stage 1 status, closure review and probe report, runs `verify_manifest.py --write`, then commits and pushes to that branch |
| Assessment | The commit message describes the job as temporary. Write permission matches its intended job and is not by itself proof of excessive privilege. The defect is a completed one-off write job remaining in the tree. It ran on human pushes to PR #1's branch, rewrote evidence-related files and pushed a commit. Its stale assertions could fail, its automatic writes could interfere with continued work, and it would enter the integration base on merge |
| Required action | Remove the workflow on PR #1 before the next substantive push to that branch, with CI on the removal SHA |
| Owner | PR #1 branch, under the PF-1.2 corrective package authorized by the operator |
| Status | Closed. PR #1 merged to main as `dddd22bbc1f080aff7ffacc7922294e83b2b22a5` (merge commit; parents `897a9d7` and `ba1bad4`); main push run 34901522336 passed. Main was integrated into `docs/production-factory-v1` by merge commit `cb4e8844c15c0a5d5686273fd363b7d324bf0f65` (parents `e44c789` and `dddd22b`), whose tree contains only `.github/workflows/verify.yml` and the Windows fixture fix. History of the removal on PR #1: Removal commit `c31167a77422c0680253cdc4818fa43c6d8b507c`, pushed together with the Windows fixture fix `ba1bad43352cfe6a2c2fb7ff9090365854eb6fa4` as PR #1 head. Because the pushed head no longer contains the workflow, the push did not trigger it. Hosted push run 34898268056 checked out `ba1bad4` and passed the python, typescript and hygiene jobs |
| Closure evidence | Recorded: removal SHA `c31167a` and exact-head push CI 34898268056 on PR #1. PR #1 merged to main (`dddd22b`), preserving its history. Integration procedure step 2 was executed by merging main into this branch (`cb4e884`), whose tree lacks the path. Local gates on `cb4e884` passed on Windows, including the research-input evidence suite (10/10). Hosted CI on the submitted PR #3 head is recorded in its PR description, avoiding a self-referential claim here |
| Scope | Removal was required before further substantive pushes to PR #1, not only before merge. Independent factory documentation work could continue while it was open. Clearing it does not clear any other acceptance or stage gate |

## Future integration procedure

This records a procedure; it does not authorize merging, retargeting or rewriting either branch.

1. PR #1: remove the temporary workflow, then review, CI and a separately authorized merge.
2. If main preserves PR #1's commits (merge commit), integrate the updated main into `docs/production-factory-v1` and review the resulting diff.
3. If PR #1 is squash-merged or rebased, transplant only the factory commits: `git rebase --onto <main-after-PR1> eddbb94a120742f77bab8e27e336a28dfdc2fab8 docs/production-factory-v1`. This rewrites the PR #3 branch and needs its own authorization.
4. Confirm the candidate tree does not contain `.github/workflows/finalize-q3-partial-evidence.yml` and does not reintroduce PR #1 content superseded on main (diff the candidate against main and expect only factory-scoped files).
5. Retarget PR #3 to main, then verify all existing gates on the final head against the current base, naming the tested SHA.

## Remaining implementation

PF-1 supplies a reviewable operating structure. PF-2 evidence/instruction automation, PF-3 supply-chain security automation and PF-4 release/monitoring controls are planned in PROJECT.md and have not been installed by this change. The existing factory must not be advertised as an autonomous or production-qualified release system.

For a new repository, use WORKFLOW.md's bootstrap procedure and create a fresh project adapter. Do not copy this migration review or Bot Trader's gates/status as generic defaults. Future global automatic installation is a separate capability, not an effect of committing these documents.

## HARM-1 harmonization record

Work order `docs/factory/evidence/work-orders/HARM-1.json` (baseline `ec8cde0`). The durable ownership map and host routes are in `docs/factory/PROJECT.md`. This section records the source-to-destination mapping and machine-specific findings.

### Source-to-destination mapping

Every rule that moved or was reduced to a reference, with where it now lives:

| Source rule (at `ec8cde0`) | Disposition | Destination |
| --- | --- | --- |
| Execution guide §1 package completion sentence | Retained as the domain completion condition; package completion routed | Guide §1; WORK_ORDER.md §5 and §7 |
| Guide §4 step 1: record branch, HEAD, changed paths, gate and decisions | Routed | WORKFLOW.md §3 ancestry check; WORK_ORDER.md §1 `baselineSha` and §6 resume; bot-implementation step 1 |
| Guide §4 step 2: read SKILLS.md | Routed | AGENTS.md repository-local workflow section |
| Guide §4 step 3: context map | Retained as a reference | Guide §4 item 2; bot-context skill |
| Guide §4 step 4: acceptance row fields | Retained (domain) | Guide §4 item 1 |
| Guide §4 step 5: real-boundary and temporal reproduction | Retained (domain) | Guide §4 item 3; bot-implementation step 3 |
| Guide §4 step 6: callers, opposite branches and mirrors | Retained (domain) | Guide §4 item 4; WORK_ORDER.md §2 |
| Guide §4 step 7: fixture authoring order | Retained (domain) | Guide §4 item 5 |
| Guide §4 step 8: focused checks, final suite once, exact-head CI | Retained (domain) | Guide §4 item 6; WORK_ORDER.md §4 runs |
| Guide §4 step 9: evidence packet | Routed | WORK_ORDER.md §4 and §7 |
| Guide §7 copied command list | Routed to the executable source | `.github/workflows/verify.yml`; PLAN.md "Verification commands" |
| Guide §7 final packet fields and labels | Routed; the "never all done" rule retained | WORK_ORDER.md §4 label table and §7; guide §7 |
| Guide §8 "work-order template may fill missing evidence fields" | Removed as a contradiction | Guide §8 routes to the mandatory WORK_ORDER.md |
| bot-implementation "use the guide's completion criteria"; restated record fields | Routed | WORK_ORDER.md §4, §5 and §7, plus the guide's domain condition |
| AGENTS.md factory checkpoint list | Routed | WORK_ORDER.md; AGENTS.md keeps the mandatory route and adds the instruction-hierarchy statement |
| CLAUDE.md repeated SKILLS.md and factory routing | Routed | AGENTS.md; CLAUDE.md is a thin adapter |
| PROJECT.md "Implementation and package acceptance" routing row | Split by owner | PROJECT.md routing table and ownership map |

### greploop provenance

The migration's source-to-design table reviewed the michaelshimeles/skills copy at `513f8a24aae6383b00356fa285144b1bc3730dc1`. That copy caps the loop through `--max-iterations`, default 10, so the ten-iteration description above is accurate for it.

The originating implementation is greptileai/skills `greploop/SKILL.md` (checked at `646e2dfad81e5157e97daecc802b68d3d2c4d1e4`). It uses a fixed five-iteration cap and has no `--max-iterations` option; otherwise the two bodies match.

The factory adopts neither cap. It keeps the WORKFLOW.md §7 budget and stalled-progress checkpoint, and reaching any cap never implies acceptance. A Greptile service, an evidence recorder and tracker integration are optional capabilities; their absence is not a factory defect.

### Local workspace and global skill findings (developer-reported, 2026-09-15)

These facts were observed on the developer machine and cannot be verified from hosted evidence.

**Stale checkout.** `C:/Users/stanf/Documents/BOT` is on `m1/contract-remediation` at `f287e22`, 180 commits behind `origin/main`.
- **Git state:** no tracked or untracked changes, no stashes, no index or HEAD lock, and no running process whose command line references the path. The last reflog entry is 2026-09-14 18:34 (commit `f287e22`).
- **Ignored artifacts:** `.venv`, `executor/dist`, `executor/node_modules` and `research/data/raw`.
- **Instruction files:** its AGENTS.md and CLAUDE.md predate the factory, and it has no SKILLS.md, `docs/factory/` or `.agents/skills/`.

It was not moved: it is another worktree, and a clean state does not prove it is unused. After confirming no one is using it, the operator can update it with:

```sh
git -C C:/Users/stanf/Documents/BOT fetch origin
git -C C:/Users/stanf/Documents/BOT switch main
git -C C:/Users/stanf/Documents/BOT merge --ff-only origin/main
```

Then reinstall dependencies there before running anything, per WORKFLOW.md §3.

**Global skills.**
- **Installed:** `~/.agents/skills` holds 26 skills: 21 from mattpocock/skills, plus find-skills and three Orca skills. The lock file targets 15 non-Claude agents; Claude Code sees only the three Orca skills, through junctions in `~/.claude/skills`.
- **Automatic selection:** manual-only skills include implement, handoff and improve-codebase-architecture. Skills that may be selected automatically include code-review, codebase-design, diagnosing-bugs and tdd.
- **Changes:** none. The skills remain installed for other projects, and no verified per-project disable mechanism was identified for the hosts in use.

### Receiving-agent handoff exercise (HARM1-7)

On 2026-09-15, with stage A and a partial evidence record committed (HEAD `11a4ba3`), the developer planted one untracked file outside the declared scope (`handoff-probe.txt`) and recorded the resume report and candidate-stage output as ground truth. A separate read-only agent was then given only the repository path and the work-order path. It followed CLAUDE.md → AGENTS.md → WORK_ORDER.md §6, ran the resume checkpoint (exit 0), confirmed with plain git, and changed nothing. The probe file was deleted afterwards.

| Item | Ground truth | Receiving agent |
| --- | --- | --- |
| Revision and branch | `11a4ba3`, `pf2/routing-evidence-checks` | Match |
| Dirty paths | `?? handoff-probe.txt` | Match; flagged unknown ownership and would not touch it |
| Outside declared scope | `handoff-probe.txt` | Match |
| Existing evidence | `records/HARM-1.json`, candidate `d2e11a9`; HARM1-1 to 1-5 and 1-8 pass | Match |
| Outstanding obligations | HARM1-6, HARM1-7, with two pending items | Match |

The agent raised six findings, dispositioned in HARM-1 stage B:

| # | Finding | Disposition |
| --- | --- | --- |
| 1 | PROJECT.md already claimed routing checks that were not yet implemented | HARM1-6 implements them; the claim now matches the checker |
| 2 | The partial record's scope was wider than the work order's, unexplained | SC-1 replaces the repeating-scope rule: WORK_ORDER.md 1.4 §4 makes each record cover its own package diff, while the checker resolves inherited scopes transitively for reviewed-change coverage and staleness |
| 3 | Stage checks compare against main's merge base, not the work order baseline, unexplained | WORK_ORDER.md 1.4 §5 explains both bases |
| 4 | Bare command-index references were hard to read | §4 defines zero-based indexes; the resume report now prints the referenced command |
| 5 | No concrete place to record a handoff | §6: under a **Handoff** heading in the pull request description |
| 6 | Non-goals, trust boundary and budget were not visible to a receiving agent | Optional work-order `boundary` field, printed by the resume report; added to HARM-1 |
