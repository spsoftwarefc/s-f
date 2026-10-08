# Work-order checklist

Status: INFORMATIVE. Version: 1.6. This is the single authoritative factory checklist for every implementation work package, whichever agent performs it. `AGENTS.md` routes here, and the `bot-implementation` and `bot-review` skills consume it; do not copy the checklist into those skills or other files. Domain rules stay in `AGENTS.md`, the normative contracts and `docs/AGENT_EXECUTION_GUIDE.md`. `tools/check_factory_evidence.py` enforces the machine-checked parts described here (see `docs/factory/PF2_WORK_ORDER.md` for exact behavior and limits).

Do not fill in a passing result before evidence exists. Do not create a parallel project plan: the work order points at existing acceptance rows and adds only what they lack.

## 1. Pre-implementation checkpoint

Before changing any code, commit a work order at `docs/factory/evidence/work-orders/<ID>.json` (registered INFORMATIVE in the inventory, with integrity regenerated). Its commit must contain no implementation. New work orders use `schemaVersion` 2; schemaVersion 1 is historical compatibility only.

| Field | Content |
| --- | --- |
| `workPackage`, `objective` | Package ID and requested outcome; link the authoritative acceptance rows in the objective or obligations |
| `baselineSha` | The full SHA the work starts from, recorded after the WORKFLOW.md §3 ancestry check |
| `scope` | Paths the package plans to change; expanding it later is reported by the resume check |
| `obligations` | One entry per obligation: `id`, `requirement`, `expectedResult` (derived independently of the implementation), `expectedBasis` (rule or finding), `proofKind` (§3) |
| `baseline` | Exactly one entry per obligation: `reproducer` or `observation` with what was `observed` at the baseline and the `method`, or `limitation` with the `reason` a baseline cannot be run |
| `structure` | §2 answers: `layers`, `representativeModules` (existing files to follow), `conventions`, `reusableMechanics` with callers, `policyOwners`, `interfaces` (inputs, outputs, side effects) |
| `boundary` | Optional but expected: `nonGoals` (list), `trustBoundary` (affected trust boundary and required safe-failure behavior) and `budget` (time/resource budget and checkpoint condition), so a receiving agent sees them without the PR |
| `declaredImpact` | SchemaVersion 2 only: project-map nodes, interfaces and evidence bindings expected to be affected; AGENTS.md/domain invariants in scope with the tests that exercise each; and the advisory `context_map --find` command plus working-tree fingerprint or an explicit limitation |
| `amendments` | Empty at declaration. Any later change to an obligation needs an entry with the obligation and reason. A later `declaredImpact` expansion needs an amendment whose obligation is `declaredImpact`; it does not waive the newly discovered impact |

Record allowed actions, unavailable credentials or decisions, dependencies and the context-map fingerprint in the pull request description.

The checker rejects a work order declared after scoped implementation began, obligations changed without an amendment, and any change to baseline entries or `baselineSha` after declaration.

## 2. Code-structure checklist

Preserve the project's established structure: Python owns strategy calculations, TypeScript owns execution authority, and CTJ stays optional. Do not impose a generic service layer. Single-caller domain logic stays where it is used.

| Before implementation | During implementation | Before handoff |
| --- | --- | --- |
| Identify affected layers and representative existing modules | Follow their naming, API shape, error handling and test organization | Review and record departures from those conventions |
| Identify reusable mechanics and their callers | Extract repeated mechanics incrementally | Verify every migrated caller |
| Locate policy and authority ownership | Keep policy, authorization and state transitions in their owning layer | Check that helpers have not acquired hidden authority |
| Declare inputs, outputs and side effects | Use explicit parameters, structured results and visible failures | Check for duplication, hidden state and swallowed errors |
| Identify the changed path that carries each declared `policyOwners` entry's policy | Keep every change inside a declared owner's layer | Name that changed path for each declared owner, or record the owner that no changed path carries |

The left column goes in the work order's `structure`. The right column goes in the evidence record's `structureReview`.

Extraction is judged, not counted. Repetition across callers is a heuristic for extracting shared mechanics, not a gate. Extract when the mechanics form a coherent responsibility with an explicit interface, and verify every migrated caller. Keep policy, authorization, error classification and state transitions in their owning layer. Treat these as structure-review findings:
- a monolithic helper that hides the flow of control;
- a helper that mutates state owned by another layer;
- helpers with inconsistent argument or error semantics;
- extraction for a single caller that adds indirection without a shared responsibility.

## 3. Proof: before and after

Choose each obligation's `proofKind` by the claim it supports:

| proofKind | Before | After | Use for |
| --- | --- | --- | --- |
| `regression-reproducer` | Failing reproducer at the real input/event boundary, failing for the intended reason | Same check passing on the candidate | Defect corrections |
| `independent-output` | Absence or prior output where useful | Output compared with an independently derived expected result | New behavior |
| `event-trace` | Prior trace or limitation | Ordered event trace with conserved quantities, restart and race cases | State machines, accounting, recovery |
| `ui-before-after` | Screenshot or recording path | Screenshot or recording path, same scenario | Only when a visible interface changes |
| `performance-measurement` | Baseline measurement on the same workload and environment | Candidate measurement with repetitions and method | Performance claims |
| `preservation-review` | Source observation at the baseline | Diff, routing and integrity review | Instructions, documents, gates |

Screenshots are required only for visible UI changes. Backend work uses traces, independent expected outputs and regression reproducers. A recording or annotation saying "passed" is not semantic verification. If the baseline cannot be run, record a `limitation` and limit the claim; never fabricate a before state.

## 4. Evidence record

After implementation, add `docs/factory/evidence/records/<ID>.json` in a separate later commit, because a commit cannot name its own SHA. A schemaVersion 1 work order continues to use schemaVersion 2 records; a new schemaVersion 2 work order uses a schemaVersion 3 record with `impactReview`. Register it INFORMATIVE in the inventory.

The checker computes the actual impact side from the real `baseSha..candidateSha` diff by calling the existing project-map impact implementation. Authors do not record `actualComponents` or similar fields. For schemaVersion 2 work orders, every computed changed node, evidence node becoming stale and downstream affected node must be included by the declaration (with interface/evidence subsets also declared) before acceptance. A discovered gap is corrected by a recorded `declaredImpact` amendment; a narrative reason is not a waiver.

`impactReview` contains only reviewed facts the map cannot derive: `invariantsRechecked` (each declared invariant plus the declared tests actually rerun), `unexpectedImpact`, `unaffectedBoundaries` with the method used, and `declarationGapReasons`. A passing label cannot retain a declaration-gap reason.

| Field | Rule |
| --- | --- |
| `workOrder`, `workPackage` | The declaring work order and its package ID |
| `candidateSha`, `baseSha` | The verified implementation commit, and the work order's `baselineSha` |
| `scope` | Must cover every path changed between this record's `baseSha` and `candidateSha`. A superseding record declares only its own package's scope; for reviewed-change coverage and post-candidate staleness, the checker resolves its own scope plus every scope in the transitive `supersedes` chain. A missing record or cycle fails closed |
| `commands`, `runs` | Exact commands with exit codes and environment. For runs, a push run tests `candidateSha` exactly; a pull_request run names its merge `testedSha` and `baseSha` |
| `results` | One per obligation: `outcome` (`pass`, `fail`, `deferred`), `after` evidence, and a `before` reference (`baseline`, `path`, `command`, `run`) or a `baselineLimitation`; a `blockedClaim` for `deferred`. A `command` reference is a zero-based index into `commands`; the resume report prints the referenced command |
| `structureReview` | `conventionsFollowed`, `departures`, `migratedCallersVerified`, `authorityCheck`, `duplicationHiddenStateErrorsCheck` |
| `impactReview` | SchemaVersion 3 only: invariant/test rechecks, unexpected impact, explicitly unaffected boundaries plus method, and any declaration-gap reasons. Actual graph impact is never authored here |
| `resultLabel` | Must be backed by the evidence it claims; see the table below |
| `supersedes`, `exclusions` | Records this one replaces; claims explicitly not made |

| Label | Required evidence |
| --- | --- |
| `CI verified`, `review-ready`, `accepted`, `released`, `operationally qualified` | A successful push run on `candidateSha`, zero-exit commands, no failed results |
| `locally verified` | Zero-exit commands, no failed results |
| `fixed` | As locally verified, plus a `before` reference for every passing result |
| `failed` | A failing command, run or result |
| `deferred with blocked claim` | At least one deferred result |
| `specified`, `implemented`, `proposed policy`, `not verified` | No passing results |

## 5. Stages

Candidate-stage runs are draft pull requests, pushes to non-default branches, and local runs by default. They report missing, stale or incomplete evidence as `PENDING`, so a candidate can be built and verified before its evidence record exists.

Acceptance-stage runs are ready pull requests (including `ready_for_review`), pushes to `main`, or `--stage acceptance`. At acceptance, the following fail:
- a change with no valid current record;
- any changed path not covered by current evidence, including files added after the candidate;
- stale evidence;
- a missing obligation result;
- a legacy record that has not been superseded.

Malformed work orders or records, self-reference, label claims without their evidence, and broken references fail at every stage.

Two different bases apply:
- **Stage checks** compare against a base derived from CI context: the merge base with the target branch, or the previous `main` tip for pushes to `main`. That base covers the whole reviewed change, which may include several packages.
- **A package's own `baselineSha`** bounds that package: its evidence record's `baseSha`, and the resume report's scope and current-record view.

## 6. Handoff and resume checkpoint

Every receiving agent, and every agent resuming after a pause, runs this first:

```sh
uv run --frozen python tools/check_factory_evidence.py --resume docs/factory/evidence/work-orders/<ID>.json
```

Before continuing, confirm each item from the report:

1. HEAD and branch match the lineage you were given (WORKFLOW.md §3); investigate otherwise.
2. Dirty paths are yours to continue. Never reset, stash-pop or overwrite another session's work.
3. Changes outside the declared scope are either amended into the work order with a reason, or stopped.
4. Obligations that already have current results have evidence that is still valid, meaning no stale or pending items against them.
5. Remaining obligations and pending items become your next actions.

Record each handoff in the pull request description under a **Handoff** heading: the revision, remaining obligations, open pending items and anything you stopped to ask. Without a pull request, put it in the package's evidence packet.

## 7. Review and disposition

| Finding | Evidence class | Impact/obligation | Correction or authorized disposition | Verification revision/result |
| --- | --- | --- | --- | --- |
| No finding must be invented merely to fill this table | | | | |

Evidence classes are reproduced, source-confirmed, policy decision and unverified.

Also record:
- changed instruction, oracle or gate review, if any;
- CI run URL, event type, full tested SHA and related head/base;
- remaining blockers, deferred claims and required external decisions;
- result level and next permitted action;
- PR or release reference, and release or activation authorization only if actually granted;
- cleanup, handoff and durable evidence location.


## 8. Semantic-impact limits

The project map is a first-class project map, not a call graph. Its current component granularity can show component/interface/evidence/gate consequences but cannot prove internal semantic chains inside one coarse node. `context_map.py` is also advisory: imports, literal references and symbol search narrow review but do not prove completeness. Therefore semantic closure remains the combination of computed map impact, declared-and-reviewed invariants, fixtures/tests, mirror/parity checks where applicable and source review. PF-2.4 does not select CI tiers and does not decompose the executor map; those are separate changes with separate acceptance evidence.
