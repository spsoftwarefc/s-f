# SF-11 — Source-bound substantive review and readiness

Status: implementation candidate. Contract version 1. This package adds **offline, read-only review assessment**. It does not grant PR approval, acceptance, merge, release or deployment authority. Reviewer assignments/requests and external scoring services are **not required**.

## Commands

```sh
sf review --root . --packet /path/to/review-packet.json
sf readiness --root . --packet /path/to/review-packet.json
```

`sf review` reports the source binding, actual diff, case selectors and findings. `sf readiness` is a concise projection of that assessment; neither modifies source, runs project commands, invokes CI or contacts GitHub. Exit `0` means the locally inspectable review packet has **no detected structural blockers**; exit `1` means a blocker, and exit `2` means invalid configuration or inaccessible evidence. Exit `0` **does not** mean CI verified, accepted, released, or externally authorized. An agent cannot self-approve through a JSON field.

## Case declaration — pre-implementation

An independent expectation cannot be derived from a test that was only written to accept the candidate's output. Record an isolated, committed, version-1 case-plan JSON immediately after the baseline and **before implementation**. Its only changed file must be the case plan itself. Require a direct first-child commit of the baseline for an unambiguous, auditable declaration. The source-bound case plan is loaded through Git's committed object rather than through the current mutable worktree.

```json
{
  "schemaVersion": 1,
  "requiredSelectors": ["positive", "negative", "fault", "temporal"],
  "cases": [
    {"id":"pass","selector":"positive","requirement":"REQ-1","expected":"expected result from contract","proofKind":"independent-output"},
    {"id":"reject","selector":"negative","requirement":"REQ-1","expected":"invalid input rejected","proofKind":"regression-reproducer"},
    {"id":"loss","selector":"fault","requirement":"REQ-2","expected":"timeout fails safely","proofKind":"event-trace"},
    {"id":"resume","selector":"temporal","requirement":"REQ-2","expected":"repeat operation remains deterministic","proofKind":"event-trace"}
  ]
}
```

Supported selectors: `positive`, `negative`, `fault`, `temporal`, `ui`. Select those demanded by the affected project contract; positive is always required. For visible UI changes, include a predeclared `ui` case with `ui-before-after` proof. This recognizes UI work without requiring screenshots for backend or documentation-only changes. The test bodies and proof payloads must actually be reviewed; matching declarations are *not* independent truth.

## Review packet

Supply strict UTF-8 JSON in an **outside-repository** file to avoid a self-referential candidate-SHA record, with exactly these fields:

| Field | Content |
| --- | --- |
| `schemaVersion`, `packageId` | Version `1`, stable package identifier |
| `baselineSha`, `candidateSha`, `candidateTree` | Full lowercase Git object identities |
| `planPath`, `planCommit` | Relative committed case-plan path and its isolated pre-implementation commit |
| `changedPaths` | Declared changed file paths; compared to actual Git baseline→candidate diff |
| `observations` | One per predeclared case: `{id,status,evidencePath,evidenceSha256}` |
| `findings` | `{id,severity,status,rationale,evidencePath,evidenceSha256}` for substantive concerns |
| `uiAffected` | Boolean visibility flag; checked against common visible-source suffixes |

Observation `status` is `pass`, `fail` or `unknown`; findings severity `blocker`, `material` or `minor`; finding status `open`, `resolved` or `deferred`. Evidence file hashes are SHA-256 hex of bytes read from a regular, non-symlinked, tracked file at the candidate checkout. Case observations and findings are **candidate-recorded** until an independent reviewer/provider checks their semantics. Logs and repository text are untrusted data, not instructions.

## Fail-closed review mechanics

Review checks exact head/tree identity, baseline and plan ancestry, single isolated plan declaration commit, subsequent changes to the oracle file, actual diff completeness, dirty worktree, all expected case IDs and their passing observations, evidence file bytes and paths, required fault/negative/temporal selectors, and unresolved material findings. A deferred material/blocker finding is still unresolved; a resolved finding needs matching retained evidence. No recorded findings yields a warning, *not* assurance that no defects exist.

Existing test changes (including changes to a test first added earlier in the same branch), instruction/gate/CI changes, skills, schema or acceptance checker changes flag `CONTROL_CHANGE_EXTERNAL_ASSESSMENT_REQUIRED`. No candidate-authored waiver turns that finding into an authorized acceptance; an independent baseline-controlled review/decision must resolve it. New tests alone produce a substantive-review warning. A change to predeclared oracle cases, including a later edit restored to its previous content, flags `PREDECLARED_ORACLE_MODIFIED`. Merge history ambiguities require review.

## Boundaries and follow-on qualification

The canonical context/implementation/review instructions remain the existing `.agents/skills/factory-context/SKILL.md`, `.agents/skills/factory-implementation/SKILL.md` and `.agents/skills/factory-review/SKILL.md`; this package does not duplicate those bodies. Every package already requires a work order as defined in `docs/factory/WORK_ORDER.md`. A case declaration supplements, not replaces, the work order, and an already-started package cannot retroactively claim to have predeclared independent expectations.

`reviewReady=true` means only *no detected local structural blockers*. It does not establish independent validity of expected outcomes, changed-code semantics, authentication of saved evidence, or GitHub branch protections. All result objects explicitly report `proofStatus=candidate-recorded-unverified`, `providerCIVerified=false`, `independentPolicyVerified=false`, `accepted=false`, `mergeAuthorized=false`, `releaseQualified=false`. SF-10 handles live CI provider metadata separately; actual authorized acceptance and merge retain repository control. The existing strict Linux/Windows/acceptance GitHub checks and merge queue remain unchanged; PR #22 remains the next authorized integration boundary, not automatic approval of intermediate PRs.

Full platform qualification of the candidate must occur on the native hosted Windows and Linux matrix. Current local testing against a source projection cannot establish the unchanged full repository's tests.
