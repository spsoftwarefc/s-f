# SF-14 — Source-bound artifact and release planning

Status: **offline development candidate; not deployment or release authority**. This package does not build artifacts, run project commands, contact GitHub, access deployment targets, apply migrations, or write output files.

## Command and inputs

`sf release plan --root SOURCE_WORKTREE --request /approved/release-request.json --artifact /artifacts/build.bin --ci-receipt /evidence/ci-observation.json --approval-pin /approved/external-release-pin.json`

The release request is a closed version-1 `sf-release-plan-request` JSON with exact fields: `schemaVersion`, `kind`, `source`, `artifact`, `ci`, `destination`, `authorization`, `migration`, and `recovery`.

- `source`: `repository` owner/name, lowercase full `commit`, `tree`. The given source root must be the exact clean Git worktree for that commit and tree.
- `artifact`: a declared SHA-256 and kind. The separately provided regular artifact file is independently read and hashed, with a strict size limit.
- `ci`: exact SHA-256 of the separately saved SF-10 provider-observation JSON, runId and attempt. The local receipt must claim correct provider metadata for this source; the offline planner does not independently refetch GitHub or prove the request's policy was protected.
- `destination`: exact targetId/environment/adapter identity, with no target network access.
- `authorization`: named principal, grantId and expiration. A JSON string is not a credential or a deployment grant.
- `migration` and `recovery`: paths of committed source-tree files, SHA-256 and explicit dispositions. Both must exactly match the bytes of the accepted source revision and the request.

An *independently authenticated operator-provisioned* external release pin must bind the exact request bytes, source SHA/tree, artifact digest, CI observation digest, destination, grant, expiry, and migration/recovery digests. Pin fields: `schemaVersion=1`, `kind=sf-externally-approved-release-pin`, `requestSha256`, `sourceCommit`, `sourceTree`, `ciSha256`, `artifactSha256`, `destination`, `grantId`, `expiresOn`, `migrationSha256`, `recoverySha256`.

## Enforcement and security boundaries

Malformed/duplicate/unknown JSON fields, unexpected paths, dirty or wrong Git checkout, missing/modified migration or recovery plan, forged/stale CI receipt, altered artifact bytes, expired approval, wrong target and mismatched pin are rejected without target writes. No source or artifact is executed. Pinned approval can only be trusted to the extent its provisioning was authenticated *outside* this CLI. A candidate that creates its own approval pin may forge both parts; matching hashes cannot independently prove source acceptance or authorization.

Success returns a deterministic `sf-offline-release-plan` with `sourceCheckoutVerified=true`, but `independentSourceAcceptanceVerified=false`, `approvedReleaseOriginAuthenticated=false`, `deploymentAuthorized=false`, `releaseQualified=false`, and `accepted=false`. Exit 0 means only that the bounded offline plan's input consistency checks passed. SF-15 must separately test authorized deployment and recovery effects, and SF-19 must qualify the release process.

One isolated work order and package evidence file precede integration. Native Linux/Windows full test suites and substantive review must be bound to PR #25's actual candidate head/base. It is stacked on PR #24 and **must not merge individually**; only PR #28 may be submitted for cumulative protected integration.
