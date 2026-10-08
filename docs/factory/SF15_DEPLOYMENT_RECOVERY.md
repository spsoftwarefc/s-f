# SF-15 — Deployment and recovery qualification (fake target only)

Status: **isolated development candidate**, not a deployer, executor, real-fencing implementation, or authorization source. This package extends SF-14 release-planning into testable simulated deployment control/recovery semantics without contacting any target.

## Surface

`sf deployment qualify --plan PATH_TO_SF14_PLAN_RESULT_JSON`

The supplied plan must match the exact closed SF-14 offline release-plan result contract. It remains deliberately **unauthenticated and unqualified**: `deploymentAuthorized=false`, `approvedReleaseOriginAuthenticated=false`, `accepted=false`, `releaseQualified=false`. The CLI reads the bounded JSON fixture and runs a fixed, deterministic fake-target matrix entirely in process. It cannot select a real deployment adapter, run commands, contact a network, mutate project/target files, issue credentials, or create a release.

## Internal state machine

An in-memory `MemoryLedger` models a recoverable journal shared by controllers; `FakeTarget` models a separate destination, monotonic fencing token, keyed idempotent dispatch receipts, observed artifact, simulated migration and health. This explicitly is NOT on-disk durable state. There is no claim of atomicity between distinct processes or devices. Fencing here is single-process logical behavior. A deployment adapter with authenticated writes is reserved for later implementation.

The simulated coordinator checks destination, principal, revocation, expiry and epoch **before** creating a prepared record. It reserves an in-memory owner/fence and records `PREPARED` with immutable intent key, exact plan SHA-256 and previous-artifact view. Simulated migration precedes a recorded `DISPATCHED` intent; fake dispatch is keyed by the same source, artifact, grant, destination, and fence identity. Returned successful receipt then permits `DEPLOYED`; health evidence permits `HEALTHY`. None of these states is a real release authorization.

Migration failure before dispatch produces `MIGRATION_FAILED`, with no target artifact. Migration changed/uncertain after an effect produces `MIGRATION_UNKNOWN` and never dispatches an artifact automatically. A crash after target effect leaves `DISPATCHED`. A lost response leaves `UNKNOWN`. Recovery consults only the fake target's exact recorded receipt and never blindly sends a new dispatch because it cannot prove a previous negative outcome. Missing/unavailable receipts stay `UNKNOWN`; a contradictory receipt blocks as `RECOVERY_BLOCKED`. Revoked/expired grants, wrong owner, wrong destination or superseded fence reject reconciliation.

Health failure yields `UNHEALTHY`; compensation is a separately requested fake action with its own persisted intent. Successful compensation is `COMPENSATED` and restores the previous modeled artifact; an uncertain compensation is `COMPENSATION_UNKNOWN` and is never automatically replayed. These are **dispositions**, not proof that a real migration could safely be reversed.

## Qualification matrix

The fixed scenarios are `healthy`, `concurrent`, `stale-authorization`, `stale-fence`, `migration-failure`, `migration-after-effect`, `crash-after-dispatch`, `unknown-outcome`, `unknown-recovery`, `health-failure`, `compensation`, `compensation-unknown`. Each requires an exact state and an independent event/dispatch-count invariant. Any failure prevents a synthetic-passed outcome. Per-case evidence includes an event trace, expected/observed status and fake dispatch count. The result explicitly labels `realTargetExercised=false`, `diskDurabilityVerified=false`, `distributedFenceQualified=false`, `externalAuthorityAuthenticated=false`, `accepted=false`, `deploymentAuthorized=false` and `releaseQualified=false`.

## Exclusions / SF-16 and SF-19 handoff

Simulated success does not authenticate SF-14's externally supplied approval pin or independently replay real provider outcomes. Not covered: actual target credential isolation, platform permissions, process/crash persistence, distributed CAS/leases, remote idempotency contracts, irreversible migrations, network partitions, reliable health observability, signed provider receipts, rollback feasibility or staged rollout. SF-16 must define incident/telemetry operations and SF-19 must qualify the complete portable factory without mistaking synthetic evidence for real deployment.

The package must be committed/reviewed on PR #26 stacked on PR #25. No intermediate merge is permitted; the cumulative integration is PR #28 after its own required PR and protected merge-group validation.
