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
