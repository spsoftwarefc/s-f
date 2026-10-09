# Threat model v0 — software factory

## Assets and authority
Project source/requirements, credentials, release destinations, exact candidate identity, work orders, execution receipts, factory package identity and evidence.

## Actors and boundaries
1. Local developer/operator: can authorize ordinary development, but its identity alone does not prove release evidence.
2. Coding agent: proposes/implements within granted scope; model output cannot promote itself to trusted evidence.
3. Candidate repository/input author: may modify code, tests, instructions, issues, manifests and logs. Candidate-controlled policy is not independently authoritative.
4. Host/CI provider: may supply authenticated run metadata but its capability must be checked, not assumed.
5. External systems: package registries, scanners, deploy targets and telemetry providers are distinct trust domains.

## Threats and required controls
| Threat | Required handling |
| --- | --- |
| Prompt injection from issue, README, transcript or log | Treat as task data; never authority or permission grant |
| Forged CI URL/status or substituted attempt | Verify provider identities, run/job/attempt, SHA and artifact |
| Candidate deletes a check or rewrites expected result | Baseline-controlled control-change review; do not accept merely on candidate checker |
| Traversal, symlink escape, stale plan or dirty collision | Strict containment and digest-checked installation plan |
| Untrusted command execution | Do not execute at discovery; command runner is not a sandbox |
| Secret leak through log/build/cache | Narrow credentials; redact retained output; release secrets outside candidate builds |
| Replay/ambiguous external dispatch | Durable record and reconcile unknown outcome before retry |
| Cost/worker runaway | Shared budgets, cancellation, serial default and bounded retries |
| Missing/unsupported host protections | Explicit advisory/unknown status, never claim enforcement |

## Control strength
Represent controls as advisory, locally-enforced, CI-enforced or externally-enforced. Local markdown and repository permissions are not tamper-proof. Administrator bypass is a residual risk.

## Reviewer policy
Substantive agent/self-review is recorded, but no assigned human, external reviewer request or approving-review count is required by s-f. Existing project platform rules cannot be silently disabled.

## Release boundary
A passing development package cannot authorize deployments. The release executor independently checks artifact identity, destination, authorization and recovery readiness.

## PQ-00 trust-boundary expansion (9 October 2026; planned mitigations, not implemented controls)

| Additional attack or failure | Required future verifier/mitigation | Package and blocked disposition |
| --- | --- | --- |
| Archive ships a replacement verifier/trust policy or correct digest under wrong GitHub signer/workflow | Pin verifier/root/policy *outside* candidate; verify issuer, repository ID, workflow/ref and artifact identity against independently owned expectations | PQ-01: reject; offline trust freshness unavailable when outside bounded validity |
| Signed old version and downgraded/root-rotated policy | Monotonic release and trust epochs; bounded expiration, controlled root rotation, documented rollback authority | PQ-01: reject unauthorized downgrade; no indefinite offline freshness claim |
| CI status URL, green candidate check, run attempt or policy gate supplied by untrusted PR | Fetch required run/job/attempt/event/source identities from provider under candidate-independent gate policy | PQ-02: reject wrong/partial/cancelled/skipped/neutral result; outage is unavailable |
| Candidate-generated approval, grant reused for wrong effect/target or grant revoked after planning | Independently authenticate and verify destination-bound grant at actual effect; atomic replay/revocation checks | PQ-02/PQ-05: deny new effect; preserve separately authorized read-only reconciliation |
| Release artifact rebuilt or replaced after CI | Retain immutable actual build bytes, toolchain/provenance/SBOM identity, digest-verified download | PQ-03: block missing/changed artifact or unpinned inputs |
| Coordinator crashes between intent and target effect; two controllers or stale backup share a fence | Local disk SQLite transaction for intent/claim, stable operation ID; authoritative target CAS/fence and reconciliation | PQ-04/PQ-05: unknown outcome blocks blind replay; multi-host WAL unsupported |
| Late worker reaches target after coordinator lease expiry | **Target** enforces monotonic generation or equivalent precondition | PQ-05: target lacking enforcement unsupported for unattended dispatch |
| Fake/late/duplicated/reordered health observation; incident history truncated | Authenticated, ordered, bounded live events and durable incident transitions; manual operator-authorized resolution | PQ-06: stale/unknown health not green; keep unresolved incident |
| Cross-profile assumption: public GitHub features used for private adopter or Linux reference passed off as all providers | Explicit capability discovery and scoped acceptance dossier, unsupported state | PQ-07/PQ-08: no blanket rollout or production label |

**Authority ownership:** the candidate author controls source and candidate-created logs only. Trust policy/verifier bootstrap, CI acceptance policy, release grant, artifact-retention authority, target-side enforcement and incident closure are distinct controls even if the same human operator administers them. A second human reviewer is not mandatory. SHA-256 equality without authenticated policy custody is not publisher authenticity. No orchestration shared-fleet safety is claimed: SF-17/18 deferred and SF-R10 unmet. See [PQ-00 contracts](../factory/PQ00_CONTRACTS.md) for prospective typed boundaries and falsification cases.
