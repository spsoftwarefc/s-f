# PQ-01A — Operator-pinned GitHub artifact attestation verifier (development candidate)

**State:** bounded source implementation in progress. **No authenticated public release, live attestation qualification or authorized installation is claimed.** This is the first (read-only) subpackage of PQ-01; PQ-01B remains the separately declared installer/effect-boundary and genuine signed-evidence qualification work.

## Design decision and why

For the current public s-f publisher, invoke GitHub CLI's supported `gh attestation verify` implementation rather than writing a new Python Sigstore cryptographic verifier. The CLI supports exact repository, signer workflow and signer revision, source ref/digest, OIDC issuer, SLSA provenance predicate, downloaded offline attestation bundle and custom trusted root checks. See [GitHub CLI](https://cli.github.com/manual/gh_attestation_verify) and [GitHub attestations](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations).

The verifier is a **separately obtained, operator-provisioned executable**. s-f checks that its exact bytes match a digest in a **separately authenticated policy** and runs a temporary, privately copied executable; policy bytes must match a second SHA-256 supplied through an independently owned operator channel. The custom root is similarly checked before invoking the verifier. Trust still depends on the operator genuinely obtaining and protecting the expected policy SHA and verifier/root bytes outside the untrusted candidate. A caller who self-selects malicious policy, digest and verifier can manufacture a green `gh` command; the CLI cannot prove policy custody and never asserts it does. Policy and verifier upgrades require deliberate operator replacement of exact digests.

The signed statement's artifact subject digest must independently match the actual ZIP SHA-256 and a separately supplied SF-13 release pin, with exact source commit/tree and release ID. Policy pins a monotonic release epoch and an expiry date; the **caller separately supplies a minimum acceptable epoch**. The code has no protected persistent last-accepted epoch and cannot itself prevent rollback by a malicious operator choosing a low floor. PQ-01B must close this with independently owned state.

### CLI (read-only)

```text
sf distribution authenticate \
  --artifact ABSOLUTE_FACTORY_ZIP \
  --release-pin ABSOLUTE_SF13_PIN_JSON \
  --policy ABSOLUTE_OPERATOR_POLICY_JSON \
  --policy-sha256 SHA256_FROM_INDEPENDENT_OPERATOR_CHANNEL \
  --attestation ABSOLUTE_DOWNLOADED_BUNDLE_JSONL \
  --verifier ABSOLUTE_PINNED_GH_EXECUTABLE \
  --trusted-root ABSOLUTE_PINNED_TRUSTED_ROOT_JSONL \
  --minimum-release-epoch OPERATOR_PROTECTED_INTEGER
```

Input policy schema v1: strict, canonical UTF-8 JSON, exact fields `schemaVersion`, `kind=sf-github-public-publisher-policy`, `repository`, `signerWorkflow`, `signerDigest`, `sourceCommit`, `sourceTree`, `sourceRef`, `artifactSha256`, `releaseId`, `releaseEpoch`, `verifierSha256`, `trustedRootSha256`, `expiresOn`. Enforce an actual expiry date, field types, exact workflow-repository relationship, digest syntax and no unknown keys. Bundle, policy and tool paths must be absolute regular files (no final-component symlinks). Artifact and retained attestation evidence are each bounded in size. No GitHub token or candidate HOME is passed to the verifier; execution uses `subprocess` with explicit argument vector (no shell), isolated temporary files and timeout. The normal Python factory runtime gains **no new Python package dependency**. The GH binary/root are not embedded in distributed portable factory ZIP bytes.

### Output semantics

Success of a pinned verifier returns a `sf-pq01a-publisher-observation` with `status=verified-by-operator-pinned-cli`, bound policy/verifier/root/attestation/artifact hashes and source/repository identity. This is an **adapter observation, conditional on operator bootstrap**, not a verified release by the wider product. `independentPolicyCustodyVerified=false`, `publisherAuthenticityQualified=false`, `installationAuthorized=false`, `releaseQualified=false` and `accepted=false` remain invariant. The synthetic test harness patches external verifier results and cannot establish live digital signatures; its positive cases must never be described as live GitHub verification.

The original `sf distribution verify`, SF-13I installer/upgrade/recover commands, local lock, SF-14 release-plan and SF-19 fixtures retain existing interpretations. `distribution authenticate` is separately invoked; **it has not been wired as a mandatory effect precondition** in `integrate` or `upgrade`. Do not call those operations publisher-authenticated because this command succeeds. PQ-01B must bind authenticated evidence to the exact bytes consumed at installer plan, apply, upgrade and restart before a production install claim.

### Future real qualification and remaining decisions

PQ-01B needs the accepted signer workflow file and revision, repository numeric ID and trusted source builder, pinned supported GH version/executable digest (Windows/Linux as qualified), operator-controlled trust root and policy digest channel, genuine published GitHub attestation bundle, retention/location/expiry, verified no-network offline strategy, CLI version compatibility, rollback epoch store and fixture-to-actual-verifier differential tests. Real signed attestation and installer-bound integration must reject wrong issuer/workflow/ref/source/digest, substituted verifier/root, expired policy, authorization bypass, replay and downgrade. Github artifact attestations for **private adopter repositories** are plan-dependent and not assumed supported on non-Enterprise Cloud plans.

**No release signing workflow, protected CI control, repository setting, cross-project installation, network request, deployment or publication is introduced by PQ-01A.** Normal PR acceptance is still required.
