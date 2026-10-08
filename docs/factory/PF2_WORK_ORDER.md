# PF-2 work order: instruction routing, preservation and evidence validation

Status: INFORMATIVE. Document version: 1.5. Disposition: IMPLEMENTED; CHANGES REQUESTED IN ACCEPTANCE REVIEW; CORRECTED BY PF-2.1; VERIFIED AND COMPLETED BY PF-2.2; PENDING ACCEPTANCE. The operator authorized implementation as one bounded package after the factory was adopted on `main`. Acceptance review of `a636a47` requested the changes recorded in "Review and disposition", and they are implemented under work order `docs/factory/evidence/work-orders/PF-2.1.json`. Acceptance of the corrected revision is still required before merge. Uses the fields of `docs/factory/WORK_ORDER.md` and the acceptance-row format of `docs/AGENT_EXECUTION_GUIDE.md` §4. It is a factory-adoption package listed in `docs/factory/PROJECT.md`, not a Stage 1 closure item and not a replacement for `PLAN.md`.

Version 1.1 records the operator-accepted review of decisions PF2-Q1..Q3; see "Changes from 1.0". Version 1.2 records the implementation clarifications and stated limits; see "Implementation clarifications (1.2)" at the end. Version 1.5 records SC-1's transitive supersession-scope correction.

## Objective and boundary

- **ID and requested outcome:** PF-2. Add executable checks that make the following fail CI:
  - broken or removed agent-instruction routing;
  - loss of preserved instruction sections;
  - unrecorded removal of required CI gates;
  - missing, malformed, self-referencing or stale evidence records.
- **Authoritative references:**
  - `docs/factory/WORKFLOW.md`: §5 (evidence record fields; merge-ref versus head runs), §6 (a candidate cannot establish its own acceptability by weakening its checks) and §8 (readiness labels).
  - `docs/factory/PROJECT.md`: the PF-2 enforcement row.
  - `docs/factory/MIGRATION_REVIEW.md`: the preservation mapping, and the rule against self-referential commit claims.
  - `docs/AGENT_EXECUTION_GUIDE.md`: §4 and §7 (final packet fields).
  - Existing ledger precedent: `docs/reviews/STAGE1_GATE_STATUS.json` with `tools/check_stage1_gate.py` (it checks that evidence paths exist and recomputes claims), and `research/data/INPUT_QUALIFICATION_STATUS.json` (evidence references use `repo-relative-path+sha256`).
- **Non-goals:**
  - PF-3 (dependency, license and security scanning; action SHA pinning) and PF-4 (release, monitoring).
  - Branch protection or required-status-check settings, which are operator settings outside the repository.
  - Any change to Stage 1 status, D1–D5, Q-status, venue qualification, holdout access or trading authorization.
  - Semantic proof of evidence content (schema validity does not show that a claim is true).
  - Verifying hosted CI run facts through the network.
  - External review services, hooks and paid tools.
- **Next permitted package after acceptance:** PF-2 implementation only.
- **Source and base:** PF-2 is stacked on the factory branch `docs/production-factory-v1`. At the start, record its actual head and its ancestry to the dependency boundary, per WORKFLOW.md §3. If PR #1 or PR #3 has merged or been rebased by then, re-derive the base instead of reusing SHAs from this document.
- **Allowed actions:**
  - Add a new check script and its unittest module under `tools/`.
  - Add one new step in `.github/workflows/verify.yml` that adds the check without removing or reordering existing steps.
  - Set `fetch-depth: 0` on the python job's `actions/checkout` step, keeping `permissions: contents: read`, so ancestry and merge-base checks have history.
  - Add committed gate-list, preservation-list and evidence-record files under `docs/factory/evidence/`, each registered INFORMATIVE in the inventory, and regenerate integrity.
  - Document the check in PROJECT.md.
  - Merging, retargeting and rebasing need separate authorization.
- **Credentials:** none are available or required. The check runs offline on the checked-out tree and its local git history.
- **Affected trust boundary:** CI gate definitions, agent instructions and evidence records. These are enforcement surfaces a candidate change could weaken.
- **Required safe failure:** a missing, unreadable or unparseable input, or unavailable git history, fails the check with a named error. It never passes silently or skips.
- **Dependencies and shared resources:** AGENTS.md, CLAUDE.md, SKILLS.md, `.agents/skills/*/SKILL.md`, `docs/factory/*`, `docs/AGENT_EXECUTION_GUIDE.md`, `.github/workflows/verify.yml`, the inventory, manifest and integrity file. Run `tools/context_map.py --paths <these> --depth 1` before and after, and record the fingerprints.
- **Budget and checkpoint:** one bounded implementation slice. Apply the WORKFLOW.md §7 checkpoint after two repair cycles without new evidence.

## Accepted decisions

| ID | Decision | Consequences |
| --- | --- | --- |
| PF2-Q1 | **Evidence records:** committed JSON, one per work package, under `docs/factory/evidence/`, following the existing ledger pattern. PR descriptions stay human-readable summaries, not the validated source | `docs/` is scanned for unlisted files, so every new record needs an INFORMATIVE inventory entry and integrity regeneration. That churn is accepted because it matches the repository's provenance rules. A record cannot name its own commit or CI run, since neither exists when the record is committed. It therefore describes an earlier candidate commit and lands in a later commit, as `STAGE1_GATE_STATUS.json` already does with its `commit` field |
| PF2-Q2 | **Required-gate list:** a committed list, checked against `verify.yml` and against the list at the merge base with the recorded base | Removal is visible and fails unless an accepted change record covers it. It is **not prevented**: a candidate controls the list, the change record and `verify.yml` together, and deleting the PF-2 step also deletes the check. Only an external control can stop that, namely branch protection with required status checks. That is an operator setting, recorded as PF-3/PF-4 or operator scope. The list must include the PF-2 step itself |
| PF2-Q3 | **Stale evidence:** enforced through ancestry and unchanged scope | A record names `candidateSha` and a non-empty `scope` path list. The check requires the candidate to be an ancestor of HEAD, and requires that no file in scope changed between the candidate and HEAD (`git diff --quiet <candidateSha> HEAD -- <scope>`). CI needs full history (`fetch-depth: 0`). Hosted run facts (IDs, conclusions, pull_request merge SHAs) are attested and format-checked only, not proven offline |

## Evidence record schema (minimum)

| Field | Rule |
| --- | --- |
| `workPackage` | Non-empty ID |
| `candidateSha` | Full 40-hex SHA; ancestor of HEAD; must not equal the commit that introduces the record |
| `baseSha` | Full 40-hex SHA |
| `scope` | Non-empty list of repo-relative, normalized paths or directory prefixes; no traversal |
| `commands` | Non-empty list of `{command, exitCode, environment}` |
| `runs` | Optional list of `{id, kind, testedSha, headSha, baseSha, conclusion}`. `kind` is `push` or `pull_request`. For `push`, `testedSha` equals `candidateSha`. For `pull_request`, `testedSha` is a merge SHA distinct from `headSha`, and both `headSha` and `baseSha` are present. A `pull_request` run is never labeled exact-head |
| `expectedOutputBasis` | Non-empty |
| `resultLabel` | One of the WORKFLOW.md §8 labels or the execution guide's `fixed`/`proposed policy`/`deferred with blocked claim`/`failed`/`not verified` |
| `exclusions` | List, possibly empty |

A record that claims a passing result while any listed `exitCode` is non-zero is an error.

## Acceptance mapping

| Obligation | Rule/source | Producer → consumer | Independent expected result | Test/evidence boundary | Required gate |
| --- | --- | --- | --- | --- | --- |
| PF2-A Routing resolves | WORKFLOW.md §1; PROJECT.md routing table | AGENTS.md/CLAUDE.md/SKILLS.md links → check | Every relative link and backticked repo path in the routing files exists; CLAUDE.md imports AGENTS.md | Temp-root unittest: removed target, renamed file, missing `@AGENTS.md` → named error | New verify step plus unittest |
| PF2-B Preservation | MIGRATION_REVIEW.md preservation mapping | Committed list of required AGENTS.md headings and skill paths → check | The absence of any listed heading or skill body is an error; additions are allowed | Unittest: deleted heading, deleted `SKILL.md` → error; added section → pass | Same |
| PF2-C Required gates present | WORKFLOW.md §6; PROJECT.md gate list | Committed required-gate list → parse `verify.yml` | Each listed step exists in its job with a non-empty `run`; jobs python/typescript/hygiene exist; the list includes the PF-2 step | Unittest: removed step, emptied `run`, renamed job, list lacking the PF-2 step → error; extra step → pass | Same |
| PF2-D Gate removal visible and recorded | WORKFLOW.md §6; PF2-Q2 | Gate list at HEAD versus the list at the merge base, plus change records → check | A gate present at the merge base but absent at HEAD is an error, unless an accepted change record names that gate. The check reports that removal is visible, not prevented | Unittest with a temp git repo: gate removed from list and `verify.yml` with no record → error; with an accepted record → pass; merge base unavailable → error, not skip | Same |
| PF2-E Evidence record schema | WORKFLOW.md §5; execution guide §7; schema above | Evidence record → check | Required fields present and typed as in the schema table | Unittest: missing field, short SHA, unknown label, pass claimed with a non-zero exit code, traversal in `scope` → error | Same |
| PF2-F Stale, self-referencing and merge-ref evidence | WORKFLOW.md §5; PF2-Q1; PF2-Q3 | Evidence record plus git history → check | Error when: candidate is not an ancestor of HEAD; any `scope` path changed between candidate and HEAD; `scope` is missing or empty; candidate equals the commit introducing the record; a `pull_request` run lacks head/base, has `testedSha` equal to `headSha`, or is labeled exact-head; a `push` run's `testedSha` differs from `candidateSha` | Unittest with a temp git repo, one case per condition, plus a fresh unchanged-scope record → pass | Same, with python-job `fetch-depth: 0` |
| PF2-G Fail closed | This work order, safe-failure field | Any input → check | Missing or unparseable files, or a shallow clone without the needed history, produce errors; no skip path | Unittest: absent `verify.yml`, invalid JSON, shallow-history simulation | Same |
| PF2-H No regression; gate change reviewed | Existing gates; WORKFLOW.md §6 | All existing verify steps | Every existing step still runs and passes on the implementation SHA. The only `verify.yml` changes are the added step and `fetch-depth: 0`, reviewed explicitly for weakening | Hosted push CI on the exact SHA; record the pull_request merge SHA separately; diff review of `verify.yml` | Full verify.yml |

Each negative test must fail for its intended semantic assertion, not through an import error, a parse error in the test itself, or a platform difference. Tests write and hash identical bytes and must not assume platform newlines. Temp git repositories must set author identity locally and must not depend on global git configuration.

## Proof required

- **Before-change baseline:** show that each negative case currently goes undetected by running the proposed check logic against the baseline tree, or state why that is unavailable.
- **After change:** all unittest cases pass on Windows (local) and Linux (CI), and the new verify step passes on the implementation SHA.
- **Per claim:** command, exit code, tool versions and tested SHA. Push-run and pull_request-run SHAs are recorded separately.
- **First evidence record:** the PF-2 implementation's own record lands in a follow-up commit that names the implementation commit as `candidateSha`, and it passes the check in that follow-up's CI.
- **Preservation:** `git diff` shows no deletions or reordering among existing `verify.yml` steps, no changes to NORMATIVE manifest entries, and no edits to contracts, fixtures, the executor, research data or Stage 1 ledgers.

## Review and disposition

Acceptance review of `a636a4721d8d10bc1739b40504d949a06a156f26` (operator-supplied, 2026-09-15): **changes requested**. The reviewer reproduced the checker's 32 tests and ran targeted probes. PF-2.1 re-reproduced findings R1–R5 against the unmodified checker before any correction; the observations are recorded in `docs/factory/evidence/work-orders/PF-2.1.json`.

| ID | Finding | Evidence class | Disposition in PF-2.1 (obligation) |
| --- | --- | --- | --- |
| R1 | A non-bootstrap change with no evidence passed (`records=0 currentRecords=0`) | Reproduced | Acceptance-stage runs require current schemaVersion 2 evidence. Candidate-stage runs report it as pending (PF21-1) |
| R2 | Evidence covering `src/a.py` stayed valid after a later commit added `src/new.py` | Reproduced | At acceptance, every changed path since the base must be covered by a valid current record, and stale scoped changes fail (PF21-2) |
| R3 | `if: false` or `continue-on-error: true` on a required step produced no error; unsupported keys were ignored | Reproduced | Unsupported workflow, trigger, job and step keys fail closed. Execution fingerprints cover `run`, `env` and `working-directory`. Triggers and permissions are checked (PF21-3) |
| R4 | `resultLabel` "CI verified" with `runs=[]` passed | Reproduced | Label-specific evidence requirements (PF21-4) |
| R5 | C4 exempted whole integrity files, so an inventory reclassification after the candidate was ignored | Reproduced at checker level | Only record-registration inventory additions and the resulting manifest digest are exempt; anything else is stale (PF21-5) |
| R6 | The header said implemented while this section said not implemented, not verified and no PR | Source-confirmed | Reconciled in 1.3 (PF21-9) |
| G1 | Before/after evidence was described but not enforced; there was no validated pre-implementation record | Source-confirmed gap | Work orders are declared before implementation and validated. Records give per-obligation before/after results or a baseline limitation (PF21-6) |
| G2 | Code-structure principles were not an explicit implementation/review checklist; the skills did not consume the factory checklist | Source-confirmed gap | `docs/factory/WORK_ORDER.md` 1.1 is the single authoritative checklist (§2 structure). Both skills and AGENTS.md route to it (PF21-7) |
| G3 | No handoff checkpoint tied revision, dirty work, scope, evidence and remaining obligations together | Source-confirmed gap | Read-only `--resume` report, required by the checklist §6 and the skills (PF21-8) |

- **Gate and instruction changes, reviewed explicitly:**
  - `verify.yml` adds `pull_request` types including `ready_for_review`, so the acceptance stage runs when a draft becomes ready.
  - `REQUIRED_GATES.json` moves to schemaVersion 2 (execution fingerprints, triggers, permissions).
  - The preserved instructions add the checklist headings and route-check the checklist and skills.
  - No existing gate step was removed or reordered.
- **Residual risks:**
  - Removal is visible and recorded, not prevented, until branch protection exists.
  - Hosted run facts and approvals are attested, not verified.
  - The checker validates form and binding, not the truth of evidence.
- **Result level:** implemented. Corrections are verified per the PF-2.1 evidence record, and acceptance of the corrected revision is pending.
- **PR/release reference:** draft PR #4. No merge, release or activation authorization.

## Changes from 1.0

- **PF2-Q1..Q3:** changed from proposed defaults to accepted decisions, with stated consequences.
- **PF2-Q2 and PF2-D:** "tampering visible" became "removal visible and fails unless recorded; not prevented". Added a merge-base comparison and the requirement that the gate list includes the PF-2 step. Branch protection moved to operator or PF-3/PF-4 scope.
- **PF2-Q3 and PF2-F:** replaced the "cannot be enforced inside the commit" default with enforcement through ancestry and unchanged scope, plus a self-reference prohibition. Added the python-job `fetch-depth: 0` gate change.
- **PF2-E:** added the evidence record schema (`candidateSha`, `scope`, run `kind` with `testedSha`/`headSha`/`baseSha`).
- **Allowed actions:** now name the `fetch-depth` change and the `docs/factory/evidence/` inventory entries. Safe failure now covers unavailable git history.

## Implementation clarifications (1.2)

Integration of the factory to `main` was authorized as one package, with PF-2 implemented afterward as one bounded package. These clarifications were resolved within implementation; they are not a separate planning round.

### C1: historical versus current evidence

- **Current records:** a record is *current* only if the change under review adds or modifies it, meaning it appears in `git diff <base> HEAD -- docs/factory/evidence/records/`. Only current records are proof for the change, and they get the full checks:
  - `baseSha` is an ancestor of `candidateSha`;
  - no self-reference;
  - its own scope covers its own `baseSha`-to-`candidateSha` diff;
  - its resolved scope (own scope plus the transitive `supersedes` chain) covers the reviewed change and is unchanged since the candidate.
- **Historical records:** every other record is *historical*. It keeps schema, run-binding and ancestry validation, but is never treated as current proof or checked independently for staleness. When a current record supersedes it, its declared scope contributes to that current record's resolved scope and is therefore included in the current record's post-candidate staleness check.
- **Preservation:** records cannot be deleted or renamed, and a record must be committed; an uncommitted record fails.
- **Supersession integrity:** every named record must be present. Scope resolution follows the chain transitively; a cycle is a named error and the affected current record contributes no coverage.

### C2: bootstrap

- **Condition:** the comparison against the base is skipped only when the base tree lacks both control lists *and* `tools/check_factory_evidence.py`. That holds only for the change that introduces PF-2. The summary line reports `(bootstrap)`.
- **Not a missing-input exemption:**
  - a base containing the checker but no lists fails;
  - a base with only one list fails;
  - missing or invalid control lists at HEAD always fail;
  - an unavailable base commit fails.
- **First evidence record:** the checker commit needs no evidence record. Records are validated when present, and the PF-2 implementation's own record lands in a follow-up commit naming the implementation commit as `candidateSha`.

### C3: base and scope selection

- **Comparison base:** derived by the checker from CI context, never chosen by the candidate or a record:

  | Event | Comparison base |
  | --- | --- |
  | `pull_request` | `merge-base(HEAD, origin/$GITHUB_BASE_REF)` |
  | `push` to `main` | `HEAD^1` (the previous main tip) |
  | `push` to another branch | `merge-base(HEAD, origin/main)` |
  | Local runs | merge base with `origin/main`, else `main` |

  Other events, a missing base ref, or unavailable history fail. An explicit `--base <sha>` exists for local diagnosis; CI uses `--base auto`.
- **Own-package scope:** every path changed between a current record's `baseSha` and `candidateSha` must fall within that record's own scope, excluding the evidence directories. Each own-scope entry must exist at `candidateSha`. A freely chosen narrow scope therefore fails when it omits one of the package's changed files.
- **Resolved review coverage:** a current record's coverage is its own scope plus the scopes of every record reached transitively through `supersedes`. The current record does not repeat those inherited paths. Reviewed paths still need at least one valid current record's resolved scope; records with errors and cyclic chains contribute none. Dependencies beyond declared paths remain the author's declaration: the check cannot compute semantic dependencies.
- **Staleness under integration:** in a `pull_request` run, HEAD is the synthetic merge. Changes merged from the base into any path in a current record's resolved scope therefore make that record stale, which matches WORKFLOW.md §3 (reverify affected integration behavior).
- **Run binding:** every run's `headSha` must equal `candidateSha`. A `push` run's `testedSha` must equal `candidateSha`. A `pull_request` run's `testedSha` must differ from `headSha` and name `baseSha`.

### Required-gate fingerprints

`REQUIRED_GATES.json` stores, for each named command step, the SHA-256 of its normalized `run` text: dedented, trailing whitespace removed, blank edges trimmed. Changing a gate's command without updating the list fails. Updating the list is visible in review. Removing a gate from the list requires a change record, compared against the base.

### Stated limits

- A present heading does not prove an instruction's meaning was preserved.
- A named step with a matching fingerprint does not prove its command still enforces the same requirement.
- The candidate controls the lists, the change ledger and `verify.yml` together, so removal is visible and recorded, not prevented. Branch protection with required status checks is the external control, and it is unavailable on this private repository's current plan.
- The change ledger's `acceptedBy` is attested text, not verified approval.
- Hosted run facts in records are format-checked attestations.
- Transitive resolution preserves and checks declared path coverage; it does not establish that any record declared all semantic dependencies it should have.
- The workflow parser supports only the block-style subset `verify.yml` uses. As of 1.3 (PF-2.1), unsupported keys at workflow, trigger, job and step level fail closed, including `if`, `continue-on-error` and `timeout-minutes`. In 1.2 some execution-affecting step keys were silently ignored (finding R3).

### C4 (found during implementation; narrowed in 1.3): integrity bookkeeping after the candidate

An evidence record lives under `docs/`, which `tools/verify_manifest.py` scans for unlisted files. Committing a record therefore requires an inventory entry, which rewrites `docs/NORMATIVE_INVENTORY.json`, `docs/CONTRACT_MANIFEST_v2.json` and `docs/MANIFEST_INTEGRITY.txt` after the candidate. Without an exemption, every record would be stale the moment it was committed.

1.2 exempted all changes to those three files. Review finding R5 showed this also hid an inventory reclassification, and manifest consistency alone cannot prove that a later inventory edit was only bookkeeping.

As of 1.3, a post-candidate change to them is exempt only when it is exactly record registration:
- **Inventory:** every candidate-time entry is unchanged and in the same order, metadata is unchanged, and every added entry is an INFORMATIVE path under `docs/factory/evidence/records/` or `docs/factory/evidence/work-orders/`. Work-order registration was added in 1.4 under PF-2.2: registering a later package's work order after an earlier candidate is bookkeeping too, and without it a multi-package pull request staled its earlier evidence.
- **Manifest:** everything except the inventory digest is unchanged, including the normative `files` entries.
- **Integrity file:** follows the manifest.

Any other change makes the record stale. The three files still count for scope coverage, and regression tests cover allowed registration, inventory reclassification and stale changes to other scoped files.

### C5 (1.3): candidate and acceptance stages, work orders, results and resume

These were added under PF-2.1 in response to the acceptance review:
- **Stages:** stage selection from CI context, with acceptance-only completeness requirements.
- **Work orders and results:** pre-implementation work orders, schemaVersion 2 evidence records with per-obligation before/after results and a structure review, and superseding of legacy records.
- **Labels:** label-specific evidence requirements.
- **Handoff:** the read-only `--resume` handoff report.

The operating rules are in `docs/factory/WORK_ORDER.md` (the single authoritative checklist), and the review mapping is in "Review and disposition".


### C6 (1.6 / PF-2.4): semantic-impact binding

PF-2.4 connects the existing project-map impact query to the factory evidence lifecycle rather than creating a second impact system. New work orders use schemaVersion 2 and declare expected map nodes/interfaces/evidence bindings plus affected invariants and their tests. New matching evidence records use schemaVersion 3. The checker computes changed/stale/downstream map impact from `baseSha..candidateSha`; computed impact missing from the declaration is pending at candidate stage and fails acceptance until the declaration is amended. Human `impactReview` data is limited to invariant rechecks, unexpected impact, unaffected-boundary methods and declaration-gap reasons; it does not author the actual graph side. Historical work orders/records are not backfilled. `resultLabel` remains the only disposition system. The project-map granularity and context-map discovery limits remain explicit, and this package does not implement CI tiering or executor-map decomposition.
