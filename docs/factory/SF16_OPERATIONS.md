# SF-16 — Operations, incident handling and feedback (offline)

**Status: development candidate — not a production observability system or incident authority.** SF-16 adds deterministic read-only classification of source-bound, caller-provided observations. It does not monitor live infrastructure, send notifications, open tickets/PRs, run deployment/migration/recovery commands or override target-project incident ownership.

## CLI and contract

`sf operations assess --qualification SF15_OUTPUT.json --policy OPERATIONS_POLICY.json --observations OFFLINE_OBSERVATIONS.json`

The three inputs are bounded, regular, nonsymlink local UTF-8 JSON files (max 256 KiB each). Duplicate/unknown keys, missing schemas, unbounded observations, unsafe identities and inconsistent sources fail closed. No credentials, arbitrary raw telemetry text, URLs, shell commands, external IDs with path characters, or hosted provider integrations are accepted. This command does not write output files. It emits one machine-readable JSON report to stdout.

The qualification must be a complete **SF-15 fake-target qualification**, not a verified live deployment: all 12 synthetic scenarios must be present with success claims, and `realTargetExercised`, `accepted`, `deploymentAuthorized`, `releaseQualified`, external authority/disk/distributed fencing fields remain false. Its source commit, target and `planSha256` bind the policy and observations exactly. A fabricated locally supplied SF-15 result does **not** become provider-authenticated evidence by satisfying this validator.

### Version-1 policy

- `schemaVersion: 1`, `kind: sf16-operations-policy`
- Exact `sourceCommit` (40 hex), `planSha256` (64 hex) and `destination` (targetId/environment/adapter) from the SF-15 qualification.
- `maxEventAgeSeconds` 30–86,400, `maxEvents` 1–128 and `recoveryHealthyCount` 2–5.
- Exact `routes` for `deployment`, `health`, `migration`, `recovery`, each with a repository-configured `ownerId` and `runbookId`. IDs are routing references, **not authenticated human assignments or executable paths**.

### Version-1 observations

- `schemaVersion: 1`, `kind: sf16-offline-observations`, and the same exact source commit, plan digest and destination.
- `events`: chronological bounded rows with only `eventId`, `observedAt` (UTC seconds, `Z`), `domain` (one of the four domains), `state` (`healthy`, `degraded`, `failed`, `unknown`), and `evidenceSha256`.
- Duplicate event IDs, out-of-order/future UTC times, unsupported domains/states and invalid digest fields reject the *whole snapshot*. No sampling silently truncates observations. Event evidence SHA is a **claimed reference only**, not independently downloaded or verified evidence.

## Health and incident rules

A domain with no observations or only stale observations is **unknown**, never green. A fresh solely healthy observation yields `healthy-observed`, always marked `unverified-offline-snapshot`, not confirmed infrastructure health. An anomalous (`degraded`, `failed`, `unknown`) observation creates an incident candidate with deterministic severity (failed: critical; unknown: high; degraded: medium), configured owner and runbook. All four domains produce at most four incident candidates and four work-item proposals per evaluation.

A subsequent healthy reading does not auto-close an anomaly. Only two or more consecutive fresh healthy readings (or the policy threshold) make the incident *eligible for a manual recovery review*. The incident remains unresolved, and its proposal ID persists across an appended observation history containing the original anomaly. Stale health after an anomaly remains unknown and keeps the incident open for review.

Stable candidate IDs are derived from the bound plan digest, domain and first anomalous event ID, and so are deterministic for an **unchanged complete input history**. There is no durable, authenticated append-only observation store in SF-16: replacing/truncating history can change candidate IDs or conceal incidents. Operator-owned incident-state storage and history integrity are external dependencies, not guarantees from this stateless classifier.

## Runbooks and handoff

The report returns a `health` array, `incidents` with severity, unresolved disposition, configured owner/runbook and recovery eligibility, and `workItemProposals` that reference the incident, source SHA, plan SHA, first bad evidence digest and same routing. These are bounded proposed next work packages; no ticket, issue, notification, acceptance, deployment, incident resolution or production rollback is executed or authorized. Operators must verify the originating observation channel, current source and deployment state, ownership and runbook before recording actual incident disposition. A manual acknowledgement is **not** inferred from the JSON.

CLI exit 0 means a valid *locally observed* all-healthy snapshot, still unauthenticated. Exit 1 means valid input with missing/stale observations or incident review required; exit 2 means invalid inputs. An unavailable input cannot be silently treated as a successful check.

## SF-19 qualification exclusions

SF-16 does not establish monitoring integrations, live target health, alert delivery, paging, durable incident ledger, operator attestations, production runbook execution, independent observation provenance or feedback ticket creation. It is a deterministic developer/offline fixture and must be evaluated in the final SF-19 campaign with falsification tests and exact source/CI evidence. SF-17/SF-18 remain optional/deferred; **PR #28** remains the only permitted next `main` merge after protected acceptance.
