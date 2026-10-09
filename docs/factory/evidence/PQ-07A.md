# PQ-07A — scoped production qualification dossier readiness

**Status: source-only implementation candidate; production qualification remains BLOCKED.**

## Protected preceding source incorporation

- PQ-01B through PQ-06 source packages were combined as [PR #38](https://github.com/spsoftwarefc/s-f/pull/38) and protected squash-merged 9 October 2026 07:14:13 UTC.
- Exact protected main source baseline: `766509f380b901a8672d7ee7b2137ef28a234685`, tree `dad41cd34963d3b30a05338cb6ebd7798cc2725b`.
- PR-stage validation [run 37897202944](https://github.com/spsoftwarefc/s-f/actions/runs/37897202944): Linux and Windows each 376 tests (zero failures/skips) plus dependent acceptance, all success.
- Protected [merge-group run 37897557665](https://github.com/spsoftwarefc/s-f/actions/runs/37897557665): success on exact merge-group / merged-main SHA `766509f380b901a8672d7ee7b2137ef28a234685`.
- PRs #33–#37 closed as incorporated, **not individually merged**. Existing production qualification boolean fixtures remain false; SF-R10 remains unmet.

## New PQ-07A scope and disallowed claims

- New optional `sf.production_dossier.read_dossier / assess_dossier` APIs validate bounded, strictly versioned candidate, profile, claim names, digest/source binding and unsupported reference scopes. Each input evidence record remains a **candidate assertion**, even if its label says an issuer or its SHA matches.
- All-required present source inputs yield `present-unverified`, **never** `accepted` or `productionQualified`. A claim's source/tree/artifact mismatch becomes `identity-rejected`, missing is explicit. Cross-platform and actual production environments remain unsupported for this reference dossier.
- In scope only: disposable single-host Linux **test** reference profile. This is a structural/readiness assessor, **not** the real PQ-07 acceptance campaign.
- No genuine publisher-signed attestation, independent verifier/policy custody, release grant/revocation/replay store, signed SBOM/provenance, real process-failure and restore proof, authenticated reference service, production health/incident history or authorized adopter pilot has been supplied.
- New source tests cover absent claims, all candidate assertions still unqualified, wrong identities, invalid/duplicate claims, forged `authenticated` status, invalid JSON and unsupported profile. Test execution and exact hosted run statuses for this new PR are pending.

**Remaining PQ-07**: independently obtain and test real required evidence, retain raw bytes and verifier results, establish live experiment durations/thresholds in advance, and record scope-specific acceptance/NO-GO. **PQ-08** publication and adopter pilot remain separately gated and unstarted.
