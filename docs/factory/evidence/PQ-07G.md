# PQ-07G — raw evidence inventory intake (source candidate)

**Baseline:** protected PR #44 main `5d042208a148f9b75a429b11c8fe63f1ccef65d0`, tree `c595fe547147edfd0d0bd7ef158778d4d680ff53`. Scope: `src/sf/campaign_intake.py`, its tests, this evidence note and the work order.

## Behavior

`inspect_campaign` takes separately supplied exact source commit/tree, artifact/policy and manifest digest, rehashes a canonical manifest, enforces a Linux disposable single-host test profile, requires only the frozen PQ-07 claim oracle, and checks bounded positive/negative raw files. It rejects duplicate/unknown claims, changed proof bytes, symlinks or file aliasing. Missing files are reported rather than promoted.

This is **local byte integrity and coverage**, not a verified issuer: even a complete manifest returns `productionQualified=false`, `publishAuthorized=false`, `releaseAuthorized=false`, `adopterPilotAuthorized=false`. The candidate-supplied `issuer` is strictly a label. Source-controlled code or manifests must never define their own trusted acceptance policy.

## Verification and unresolved external gates

Unit tests exercise complete-but-untrusted cases, missing proof, substitution, alias, wrong source/policy/scope, duplicate cases, malformed manifest and unsafe symlinks. Hosted PR/merge-group checks have not been attributed here pending exact provider results.

Remaining: independently controlled trust root/verifier, real signed producer evidence and protected CI checks, grant/revocation/replay authority, immutable retained artifact, authorized disposable live target and operator-owned incidents; SF-R10 unmet. Local path safety checks are not an atomic sandbox against a malicious concurrent filesystem writer.

**Disposition:** source candidate only; no live PQ-07 campaign, PQ-08 publication or adopter pilot performed. Merge checkpoint is PR #50, not this stacked package.
