# SF-10 — GitHub Actions CI evidence metadata verification

Status: **implementation candidate**. CLI operation: `sf evidence verify`. This verifier does **not** create, rerun or approve CI, change GitHub rules, authorize a merge or deployment, or make an offline snapshot into authenticated proof.

## Operator-selected input

Versioned strict JSON request, example using an actual completed historical PR event for this repository (replace IDs and SHAs for a current candidate; do not reuse an old run as proof for changed source):

```json
{
  "schemaVersion": 1,
  "repository": "spsoftwarefc/s-f",
  "runId": 37778696498,
  "attempt": 1,
  "workflowId": 378322226,
  "workflowPath": ".github/workflows/sf07-qualification.yml",
  "event": "pull_request",
  "candidateSha": "f0caa42a8d85b0c9520427d965ebc08446817e0b",
  "baseSha": "2f0ae73ce49676d677d0071ae0ef81fbc2c86d83",
  "pullRequest": 18,
  "requiredJobs": [
    "sf07-portability (ubuntu-24.04, py3.12)",
    "sf07-portability (windows-2022, py3.12)",
    "sf07-acceptance"
  ],
  "requiredArtifacts": []
}
```

Run on demand:

```sh
sf evidence verify --request .factory/ci/expected.json --source github
sf evidence verify --request .factory/ci/expected.json --source offline --snapshot .factory/ci/provider-copy.json
```

GitHub mode performs **read-only, explicit** API calls to `api.github.com` for the selected repository and IDs. For private repos, supply `GITHUB_TOKEN` or `GH_TOKEN` through a protected process environment; neither is serialized into output. The token is *not* taken from candidate issue text or downloaded instructions. Requests use HTTPS/TLS with normal certificate verification, timeouts, bounded JSON, disabled redirects, fixed REST paths and a default-deny URL input surface. No network request occurs during CLI discovery, request validation or offline mode. A host proxy, repository administrator or manipulated GitHub API account remains outside this verifier's threat guarantees. The verifier does not run the checked project, its CI, or any command declared in the profile.

## Exact outcome contracts

The request is a closed `schemaVersion=1` contract. It requires the exact source repository, run ID and attempt, numeric workflow ID and file path, event (`pull_request` or `merge_group`), full candidate SHA, required named jobs and optional required artifacts with externally specified `sha256:` digests. For PR events, exact current PR number and base SHA are also required. Invalid/unknown fields, duplicate JSON keys, unsupported events and malformed identifiers are rejected. Saved snapshots are bounded but untrusted and can **never** satisfy provider verification.

When GitHub metadata is available, verify: repository and head repository; workflow ID/path; event; run ID/attempt; run head SHA; exact canonical run/job/check-run URLs; completed/success run and every returned job (including apparently optional jobs); correct job run/attempt/SHA; unique required job names; complete bounded job/artifact pagination; for PRs, provider run PR head/base and the **current** PR head/base/branch and repositories. Any PR head/base movement makes a historical run stale for the requested current candidate. When a required artifact is declared, verify identity, unique name, run association, expiry, nonempty size and provider-reported digest plus canonical archive URL.

For `merge_group`, the run's `head_sha` is the **observed merge-group SHA**. GitHub's run/job response is not an independent attestation of which PRs/baseline formed that commit, so the `baseSha` and `pullRequest` fields **must be null** and base membership remains unknown. A separate authoritative event/build source is required before claiming queue composition. Neither event type proves checked-out `GITHUB_SHA`/tree solely from run/job metadata; candidate-controlled logs mentioning SHA are not authenticated checkout provenance. A provider-reported archive digest is **not** a byte-for-byte download validation or authenticated build provenance.

| Outcome | CLI exit | Meaning |
| --- | --- | --- |
| `provider-metadata-verified` | 0 | GitHub API run/job/(declared) artifact metadata matches request. **Not** acceptance, checkout-tree attestation, or independently trusted required-check policy. |
| `blocked` | 1 | Provider evidence contradicts at least one required identity/job/artifact condition. |
| `present-unverified` | 1 | Offline/manual snapshot is readable JSON only; has no provider authenticity. |
| `unknown` | 2 | GitHub unavailable, incomplete response, pagination error or response cannot be inspected. |
| Invalid request/configuration | 2 | Fail-closed error, no evidence verification. |

Outputs always carry `accepted=false` and `independentPolicyVerified=false` when structured; only SF-11 and the repository's independently established acceptance policy may decide final acceptance. The request-selected `requiredJobs` is **not** evidence that these jobs are required by a protected branch or immutable policy. A valid metadata result can be stale when its controlling policy, source inputs, workflows, or claimed integration tree change. Requalify the relevant candidate; don't reuse green receipts based only on a matching branch name.

## Negative qualification / limits

Synthetic isolated regression cases check forged provider and check-run URLs, wrong run and workflow identities, substituted attempts, wrong source SHA, stale PR head/base, partial/skipped/neutral/cancelled/failed jobs, malformed/duplicate/absent named checks, wrong/expired/missing artifacts, pagination incompleteness, strict input validation, offline-mode nonpromotion and unsupported merge-group composition claims. GitHub provider read tests use an injected in-memory fake; they make zero real API calls and do not generate Action minutes. Complete native Windows/Linux qualification must be demonstrated by the exact candidate PR checks.

This is a **metadata verifier**. Future assurance must establish baseline-controlled required-check policy, checked-out tree identity, code and test integrity, artifact-byte provenance and any needed release qualifications. It does not bypass `spsoftwarefc/s-f`'s existing strict required status checks, merge queue, zero required approvals, or the user's PR #22 merge boundary.
