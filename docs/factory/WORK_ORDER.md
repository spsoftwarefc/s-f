# Work-order checklist

Status: INFORMATIVE baseline contract. Version: 2.0-draft.

This is the repository-local checklist for an implementation work package. It defines what must be declared and evidenced; it is not itself executable enforcement. Later s-f packages will formalize this contract in versioned schemas and CLI validation.

## 1. Declaration before implementation

Before changing implementation files, commit a work order. Markdown is accepted during SF-00; later schema-backed formats may replace it without changing the semantic obligations.

A work order records:

| Field | Required substance |
| --- | --- |
| ID and objective | Stable package ID and the requested outcome |
| baseline | Exact source revision/tree the package starts from |
| non-goals | Explicitly excluded behavior and effects |
| allowed scope | Paths/components the package may change |
| requirements | Project-owned requirement/decision references |
| obligations | Independently stated expected results and proof kinds |
| dependencies | Packages, interfaces, tools or external decisions required first |
| structure | Affected layers, representative modules, ownership and interfaces |
| declared impact | Expected components, interfaces, evidence and invariants affected |
| budget | Time/compute/CI/retry/storage constraints |
| authority boundary | External effects that are not authorized by implementation work |

Implementation that materially precedes its declaration is a process defect. If scope or obligations change, record the amendment and reason rather than rewriting history silently.

## 2. Structure review

Before implementation, identify the existing architecture that owns the change. Do not impose a generic layering model on a target repository.

Review affected layers/components and representative modules; reusable mechanics and callers; policy, authorization and state ownership; public interfaces and side effects; error propagation and cleanup ownership; and duplicated or hidden state.

During implementation, keep policy in its owning layer and make side effects explicit. Before handoff, record deviations from existing conventions and verify migrated callers.

## 3. Proof matched to the claim

| Proof kind | Before | After | Typical use |
| --- | --- | --- | --- |
| regression-reproducer | failing behavior at the real boundary, or a recorded limitation | same scenario passes for the intended reason | defect correction |
| independent-output | prior/absent output where useful | independently derived expected output matches | deterministic behavior |
| event-trace | prior trace or limitation | ordered trace including failure/restart/race cases | stateful behavior |
| ui-before-after | same visible scenario | same scenario after change | visible UI only |
| performance-measurement | baseline on same workload/environment | candidate measurements with method/repetitions | performance claims |
| preservation-review | source observation | diff/routing/ownership review | instructions, policy and docs |

A screenshot is not backend correctness. A green test count is not semantic acceptance. If a baseline cannot be executed, record the limitation and narrow the claim.

## 4. Candidate evidence

Evidence for a candidate records the work package and work-order path; candidate and baseline revisions; changed paths; exact local commands and exit codes; hosted run/job/attempt identifiers only when hosted evidence is actually used; before/after bindings; structure review; unexpected impact; explicitly unaffected boundaries; failed/deferred/unavailable/unknown checks; exclusions; and blocked claims.

Evidence must be source-bound. A later acceptance-affecting edit invalidates affected evidence. A record cannot truthfully name its own future commit; record completed candidate evidence in a later commit or external immutable store.

## 5. State labels

Use precise labels:

`discovered -> specified -> ready -> implementing -> locally verified -> CI verified -> accepted`

Failure, cancellation, stale evidence and blocked prerequisites are explicit dispositions. Release and operational qualification are separate progressions.

`CI verified` requires verified provider evidence for the actual candidate/integration identity. Missing, skipped, neutral, cancelled or inaccessible required checks are not success.

## 6. Handoff and resume

A receiving or resuming agent first establishes exact HEAD/base/target and dirty paths; the active work order and amendments; changes outside scope; still-current evidence; remaining obligations/blockers; and the compute/CI/retry budget.

Do not reset, overwrite or absorb unrelated work to make the package appear clean. If lineage is stale or scope changed, reconcile it before further implementation.

## 7. Review and disposition

Review the actual diff and candidate, not the implementation summary. Record each finding with its evidence class, affected obligation, correction/authorized disposition and verification result.

Evidence classes are: reproduced, source-confirmed, policy decision and unverified.

A substantive self-review is required. Assigned reviewers, approving-review counts, third-party score thresholds and external review services are not universal factory prerequisites. Existing target-repository rules remain in force until an authorized configuration change alters them.

## 8. Control changes

Changes to instructions, tests, gates, schemas or release controls require explicit review of whether the candidate weakens the mechanism used to accept itself.

Baseline-controlled or separately reviewed validation is stronger than candidate-controlled validation. Deleting a test or changing an expected result to match an implementation does not prove the implementation correct.

## 9. Resource discipline

Use focused local checks during development, then one applicable final local acceptance pass on a stable candidate. Trigger hosted CI only when it proves a hosted/provider/integration claim.

Do not rerun an unchanged passing suite for presentation. Two repair attempts without new evidence trigger diagnosis; they do not convert failure into acceptance.

## 10. Semantic-impact limits

Dependency graphs, import maps and text references are discovery aids. They do not prove semantic completeness, dynamic-dispatch coverage or absence of hidden authority.

Semantic closure combines declared impact, actual diff review, affected invariants, independent tests/fixtures, interface/caller inspection and source-bound evidence. Missing information remains unknown.
