# SF-19 — Cumulative factory v1 qualification and protected integration

**Status: development-source integration candidate; public/production v1 release BLOCKED.** Green source tests, merge checks or synthetic outcomes cannot authenticate publisher trust, release permissions, durable recovery or live operations.

## Exact ancestry

Historical protected main baseline from PR #22: `6c82b1230046650afcf28a61d7c8da7f8d157773`. PR #28 is the *one* cumulative candidate based on `main`, building on the full PR #23–#27 stack without individual merges. Its first isolated work-order commit `53c99cacf1b0de319e471d6941a5981c45960b50` derives from exact PR #27 head `a4a8ab734a34d408a6c6e0b0ca6d81a9a980ec70`, tree `df0620c35c6b7b2263f366bea1d08f2e9bb321d5`.

## Offline cross-package qualification

`sf factory qualify --target TARGET --bundle ZIP --trust PIN --lock LOCK --release-plan PLAN.json --deployment SYNTHETIC.json --operations-policy POLICY.json --observations EVENTS.json [--as-of 2026-10-08T20:00:20Z]`

The operator must authenticate the digest pin outside the program; a matching checksum or locally generated lock is not signing or issuer authentication. The command is read-only and validates:

1. Independently recheck canonical source archive, external pin and exact lock; compare the installed release record and source manifest.
2. Independently reconstruct every generated and portable owned path and rehash actual target bytes, including binary members. Reject changed/missing/symlinked owned files, altered source, or a pending installer transaction. Leave all foreign instructions and project-owned CI untouched.
3. Bind source commit/tree and archive SHA to the unqualified SF-14 release plan. Its CI and release-approval snapshots are caller-provided and **not independently reverified**.
4. Recompute the 12 SF-15 fake-target scenarios for this plan and reject forged/stale deployment qualifications; no actual target effect is performed.
5. Recompute SF-16 source/target-bound UTC operational observations and incident proposals, including missing/stale/unknown health. Incidents and suggested work are never executed or auto-resolved.

Successful output is `sf19-factory-development-qualification`, `developmentFixturePassed=true`, and `installedOwnedBytesRechecked=true`. This is not a public v1 release. All authorization outputs remain false: `accepted`, `mergeAuthorized`, `productionReady`, `releaseQualified`, `deploymentAuthorized`, `publisherAuthenticityVerified`, `externalReleaseAuthorityVerified`, `independentCIVerified`, `realDeploymentExercised`, `durableRecoveryVerified`, and `liveOperationsVerified`.

## Source integration gate

Before *any* merge, review the actual source/contract changes, confirm work orders and ancestry, and require a completed successful PR #28 Linux and Windows Python 3.12 full suite (zero failures, errors, skips) plus required `sf07-acceptance` for its exact head and current `main` base. PR-stage verification is insufficient for protected incorporation. Only PR #28 may join the ordinary GitHub merge queue. Its separate `merge_group` run must pass the same required jobs on the exact queue checkout SHA/tree; verify `main` actually advanced. Never bypass protection, perform a direct merge, or individually merge upstream PRs #23–#27. Once GitHub confirms protected integration, prior stacked PRs may be closed as incorporated, *not* marked individually merged.

## Production qualification blockers and deferrals

Product/public v1 readiness is **not attained** until publisher signing and authenticated trust-pin custody; independent CI/release authority; real provider deployment with limited credentials and verified health; disk-durable, multi-process idempotent fencing/recovery; and live telemetry, durable incident ledger and authorized operator runbooks are independently established. Optional SF-17/18 agent orchestration and budget/concurrency qualification remain deferred; SF-R10 is unmet. This PR provides source integration and explicit limitation evidence, not operational v1.

The test suite uses isolated, temporary synthetic Git source and target fixtures. No code path here modifies unrelated repositories, starts production services, deploys artifacts, issues credentials, creates incidents, or executes target commands.
