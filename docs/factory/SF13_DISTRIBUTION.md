# SF-13 — Deterministic offline factory distribution (development preview)

Status: bounded implementation candidate. SF-13 is **not** a public release, publisher-signature verifier, installation authority, deployment mechanism or SF-19 v1 qualification.

## Portable source contract

`sf distribution build --root REPO --output ../sf-preview.zip --publisher example-publisher --release-id preview-20261008`

The build is opt-in, fully offline, and uses the **clean, committed** Git HEAD (full commit/tree). It fails on a dirty/untracked source, incomplete required core, symlinks/submodules in included paths, unexpected Git stage, path alias/collision, or oversized files. It creates no directories, overwrites no output and does not run project code. The declared source payload is limited to `src/sf/*.py`, the three canonical `.agents/skills/factory-*/SKILL.md` bodies, `docs/factory/WORKFLOW.md`, `docs/factory/WORK_ORDER.md`, and `pyproject.toml`. Project-specific `docs/factory/PROJECT.md`, source-bot history, current work orders, private credentials, local test outputs and the CI evidence ledger are excluded. Extra future portable files require an explicit contract/code amendment; adding files outside the allowlist never silently adds them to the bundle.

A ZIP with sorted file entries, fixed timestamps/modes and no compression is built deterministically from the tracked object bytes. A canonical UTF-8 JSON `manifest.json` binds the claimed publisher, release id, factory version, source Git SHA/tree, supported schema compatibility and each exact path/size/SHA-256. The archive digest is **not embedded within itself**. Version `0.0.1` remains a development-preview version; it does not imply product release qualification.

## Trust and offline verification

`sf distribution verify --bundle ../sf-preview.zip --trust /protected/operator/approved-release.json --lock-out ../factory-lock.json`

Verification requires a distinct trust record **provisioned independently through an authenticated operator-controlled channel**. The trust JSON is a versioned **exact release pin** containing the full expected ZIP SHA-256, publisher, release id, factory version, source commit/tree, compatibility and expiry date. The selected manifest identities must match the independently supplied pin; every ZIP member must match its manifest's digest, size and exact allowlist. It rejects duplicate names, traversal, symlinks, unexpected files, compressed/oversized members, noncanonical metadata, mismatched identities, expired pins, and malformed/unsupported schemas. It never extracts or executes the archive and needs no network or extra Python dependency.

Trust pin example (values must be populated from a separately authenticated release authority; placeholders are **not** functional authorization):

```json
{
  "schemaVersion": 1,
  "kind": "sf-out-of-band-release-pin",
  "publisher": "your-authorized-publisher",
  "releaseId": "preview-20261008",
  "factoryVersion": "0.0.1",
  "sourceCommit": "<40 lowercase hex chars>",
  "sourceTree": "<40 lowercase hex chars>",
  "bundleSha256": "<64 lowercase hex chars>",
  "expiresOn": "2027-01-01",
  "compatibility": {
    "python": ">=3.12",
    "profileSchema": 1,
    "workOrderSchema": 1,
    "evidenceSchema": 1,
    "installationSchema": 1
  }
}
```

**Security interpretation:** Verifying an exact preapproved digest authenticates the bytes **only to the degree that the independent pin was authenticated and protected beforehand**. A candidate that supplies or modifies both bundle and trust JSON can forge this result. The verifier does not authenticate the external trust-file origin, validate digital signatures, prove source repository custody, certify SLSA provenance, or verify published archive bytes against an external transparency log. The JSON field `publisher` is an asserted label, not a signature. This is an honest digest-pinning trust model, not a signature-backed issuer identity. Those stronger controls remain qualification gaps before public production distribution.

`status: matched-external-release-pin` means local bytes and fields match the given trust configuration, **not** publisher-signature verified or accepted for release. The response explicitly reports `publisherSignatureVerified=false`, `independentTrustProvisioningVerified=false`, `sourceAuthenticityConditional=true`, `accepted=false`, `mergeAuthorized=false`, and `releaseQualified=false`.

## Installation lock and compatibility

Only explicit `--lock-out` writes a new, exclusively created lock file; no update or overwrite is allowed. The lock binds release/publisher id, exact source SHA/tree, bundle digest and exact compatibility schema versions. Installations should retain the lock and use existing SF-05/06 explicit dry-run/apply/upgrade/remove procedures **only after operator verification and an authorized installation decision**. The current SF-06 installer does *not yet* consume this lock or enforce bundle verification as a mandatory precondition. Do not claim that merely creating a lock enforces provenance across the installer. Pinning trust for target repos and end-to-end authenticated installation promotion are follow-up qualification items.

No background updates, remote API traffic, hosted agent infrastructure, releases, merge automation, credential handling, or target-repository writes occur. A changed bundle must be separately verified under an independently approved new pin. Removal retains the existing ownership-preserving SF-06 rules; this package introduces no new removal authority.

## Test boundaries and promotion

SF-13 synthetic fixtures cover identical build outputs for the same committed tree, exclusion of nonportable project files, source dirt, user-requested exclusive output, mismatched publisher/release/source version/tree/digest, expiry, duplicate/unknown JSON, corrupt members, extra/duplicate/unsafe paths, symlinks, case/Windows reserved names, zip reordering and unsupported compatibility. Native Windows/Linux full suite qualification must match the PR #22 integration candidate. A green PR is not merge-group proof. Enter the protected squash merge queue only after explicit user authorization; source and queue SHA/tree identities must be recorded separately.

## SF-13I installation-binding follow-up (development candidate)

SF-06 now has an opt-in proof-binding pathway using `--bundle`, `--trust` and `--lock` together. It revalidates an unexpired operator-pinned archive and exact canonical lock at plan/apply/recovery boundaries and records that lock identity in the plan/journal. It rejects missing or modified proof when replaying a proof-bound plan or recovering its journal.

This does **not** yet fulfill original SF-13 installation acceptance: the legacy preview path is still available, the operator-supplied trust file is not authenticated by the tool, and generated target routing/ownership files are not byte-for-byte copied from the verified ZIP. In particular `verified-external-pin-for-installation` means a conditional local lock comparison, not full installed-payload authenticity or product acceptance. Do not promote this slice until those boundaries are closed with independent tests.
