# PQ-07S — independently owned live qualification handoff (PR #57)

**Status: PREPARATION ONLY — NO-GO for production.** This is a campaign intake contract, not an authorization to issue credentials, dispatch workflows, deploy, publish or enrol an adopter. All independently authenticated live PQ-07 claims remain **UNKNOWN / NOT EXECUTED**. PQ-08 is NOT STARTED and SF-R10 is UNMET overall.

## Protected development baseline

- [PR #56](https://github.com/spsoftwarefc/s-f/pull/56) merged via protected **SQUASH** at 2026-10-09T10:03:31Z.
- Verified post-merge `main`: `a462d5306c731341c4c915797693edb8e1c71615`; tree `1ac77ead7a202eb46eaea96a6f052505297ba724`.
- [Protected merge_group run 37914839522](https://github.com/spsoftwarefc/s-f/actions/runs/37914839522), attempt 1, completed with conclusion success for that exact integration SHA.
- PR #56 integrates **source preparation** PQ-07M–R only. It is **not** a signed/published release candidate. A later qualification campaign MUST pin its own source, workflow, run/attempt and immutable artifact digest.

## External decision docket — no default approvals

An operator must supply the following **out of band**, through independently controlled resources. Names, labels, hashes and locations embedded in the proposed release repository are never authoritative. An incomplete entry is `BLOCKED`, not `approved`. The same human may operate independent resources, but an independently verified control boundary is required for every authority-bearing decision.

| Gate | Independent owner and bindings needed | Genuine proof required for closing it | Disposition now |
| --- | --- | --- | --- |
| PUBLISHER | Trust-policy owner, verifier binary/version/hash and root hash; repository ID, approved signer workflow/ref, minimum epoch and expiry | Verified genuine provenance over **consumed** bytes under that separate policy, wrong-signer and rollback negatives | BLOCKED — custody not supplied |
| PROVIDER | Protected CI/release custodian; source + merge-group SHA, workflow ID/ref, GitHub run ID and attempt, final jobs, artifacts | Fresh provider-fetched results bound to frozen release candidate; unavailable, skipped or replaced checks reject | BLOCKED — source CI is not release CI |
| GRANT | Independent issuer, revocation/replay owner; principal, operation/grant IDs, destination, allowed effect, digest, epoch, expiry | Destination-side enforcement against replay/revocation/stale epoch, and zero authority from passing PR checks | BLOCKED — no active effect grant |
| RETENTION | Separate artifact custodian, immutable address/version/access, retention/expiry, SBOM/provenance/toolchain digests | Fetch the **one built** artifact and provenance, compare exact digests and verify source; no rebuild on promotion | BLOCKED — local/GitHub preview retention insufficient |
| TARGET | Explicit disposable single-host Linux test service and custodian; least-privilege credentials, network scope, effect/cleanup budget | Authenticated remote generation/CAS and receipt, abort/retry safety, migration/rollback and testable recovery | BLOCKED — no external target authorized |
| OPERATIONS | Independent telemetry/incident and response owner, authenticated observer, max age and journal retention | Live incident and recovery evidence including replay/future/stale/forged negative tests and manual acknowledgment | BLOCKED — no authentic live observation |
| PQ-08 | Separate publication and adopter owner, target profile, rollback and pilot permit | Later authorization for exact approved bytes and isolated adopter, after PQ-07 profile acceptance | NOT STARTED |

The eight decision identifiers in `src/sf/external_readiness.py` are **declarations only**; its deliberately false `custodyAuthenticated` output must not be changed to create synthetic approval.

## Campaign activation sequence

1. **Operator work order:** outside candidate control, name the authorized disposable target, independent custodians, safety envelope, abort/cleanup ownership, allowed read/write scopes, evidence-retention and budget. No real effect without this authorization.
2. **Freeze campaign identity:** exact future release commit and tree, intended environment/profile, approved workflow identity, source merge-group SHA, provider run/attempt, immutable artifact/SBOM/provenance digests, independently custodied policy/verifier hash and expiry. Do not reuse PR #56's development SHA as release approval.
3. **Validate supply chain and permission separately:** execute/observe signing only under the independent publisher policy; obtain fresh CI evidence and an externally controlled scoped grant. Verify both at the effect consumer, not in a candidate-generated report.
4. **Consume retained bytes without rebuild:** compare exact stored/downloaded bytes to operator-held pin. A seven-day GitHub preview artifact or SHA-256 by itself is insufficient custody.
5. **Exercise live reference target with controlled faults:** installed/upgrade/remove, transaction intent before effect, lost reply, kill/restart, competing worker, remote fencing/CAS, database contention, stale backup, migration/health failure and compensation. `UNKNOWN` forbids unattended retry; record authoritative target state.
6. **Verify authenticated observation and incidents:** verify observer identity, ordering, freshness, replay resistance and persistent unresolved incidents; manual owner resolution only.
7. **Independent campaign disposition:** positive and deliberately wrong/stale/forged negative results for every in-scope claim, operator-pinned raw evidence/attempts and an explicit qualified profile or NO-GO. Never infer multi-host/agent SF-R10.
8. **Separate PQ-08 decision:** only after a genuinely accepted PQ-07 profile, approve publication and adopter pilot in their own work order. No automatic elevation.

## PR #57–62 sequencing

| PR checkpoint | Work package | Source deliverable / dependency | Runtime authority |
| --- | --- | --- | --- |
| **#57** | PQ-07S | Reconcile genuine PR #56 / merge-group; freeze this activation docket, gaps and stack design | Documentation, NO-GO |
| **#58** | PQ-07T | Source-only operator-bound campaign intake: strict external pins, candidate/profile freshness and negative-case constraints, preserving unqualified outputs | Read-only until actual external proofs provided |
| **#59** | PQ-07U | Authenticated publisher / retained-byte / provider handoff review: exact original digest and separate policy provenance boundaries; reject source self-approval | Verification only; no release grant |
| **#60** | PQ-07V | Reference deployment and recovery interface: explicitly authorized disposable target, destination-side CAS/receipt and crash/restore scenario contracts | **Live execution blocked** until target and grant separately authorized |
| **#61** | PQ-07W | Authentic incident/operations evidence and cross-boundary qualification disposition/negative oracle | No auto-closure or self-qualification |
| **#62** | PQ-07X | Cumulative source-diff review and evidence reconciliation, protected squash merge-group integration **only if exact-head CI passes** | Source merge only; no PQ-08 |

The numbering is an **intended PR sequence**, not an assertion that future PRs exist or that independently controlled facts are available. Each work order is committed before its implementation, one active PR/branch writer at a time, dependent branches pinned to the preceding head. PRs #57–61 remain draft and must not be independently merged. The user set the next protected integration checkpoint to #62; this does **not** preauthorize any live operation.

## Stop conditions and resource controls

Stop any live execution and report `NO-GO` if a custodian, independent pin/identity, immutable evidence store, replay/revocation enforcement, remote fence, health observer or recovery owner is absent, expired, contradicted or unauthenticated. A local process-death example, CI-green label or manually built preview provenance cannot turn a missing fact into PASS.

No production VPS, unrelated repository, paid hosting, automatically triggered release or target modification in source-only packages. Prefer local focused checks. Hosted checks are required on actual PR/merge-group identities, but never rerun an unchanged green candidate for cosmetic reasons. Do not weaken the repository's required Linux, Windows and `sf07-acceptance` gates or create mandatory reviewer requirements.

Related: [external activation contract](PQ07_EXTERNAL_ACTIVATION.md), [live reference runbook](PQ07_REFERENCE_RUNBOOK.md), [production qualification plan](SF_PRODUCTION_QUALIFICATION_PLAN.md).
