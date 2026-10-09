# PQ-00 — Qualification claims, typed boundary contracts and acceptance oracle

**Type:** design/requirements contract, not implemented runtime schemas. **Baseline:** `45a1d78197667efeedf5f2e60ca07f1ff070a6f6`. **Status:** proposed for PQ-00 review. The actual versioned JSON/CLI contracts and adapters are implemented, independently tested and frozen by their owning PQ-01–PQ-06 work orders. Changing these commitments then requires a documented amendment and acceptance impact review; merely editing this markdown cannot confer authority.

## A. Claims and non-negotiable invariants

1. **Development vs production:** `developmentFixturePassed`, `installedOwnedBytesRechecked`, protected source merge, checksum match and simulated recovery are not `releaseQualified` or `deploymentAuthorized`. Existing SF-13I/SF-14/SF-15/SF-16/SF-19 fixture outputs/booleans remain unmodified.
2. **No self-certification:** candidate-provided verifier, trust policy, CI expectation, approval pin, release grant, telemetry or status record cannot authenticate itself. The verifier binary/version, trust roots/policy and acceptance criteria must be provisioned outside the untrusted release/candidate artifact.
3. **Identity before status:** check immutable repository ID and canonical name, commit/tree, workflow identity/ref, run/attempt/event/head/base/merge-group, accepted artifact SHA-256 and provider status against independently controlled policy. An inaccessible dependency is **unavailable** rather than green.
4. **Authority at effect:** valid artifact or successful tests do not grant a write. Any release/installation/deployment/compensation/migration effect checks authenticated principal, exact destination/environment, allowed action, artifact and manifest, policy and grant versions, expiry/revocation/replay **immediately before that effect**.
5. **Durability before dispatch:** persistent immutable intent and stable operation identity precede any target mutation. A locally incremented lease that the target does not enforce is not fencing. Unknown outcome is reconciled before any retry; never promise cross-system atomicity or globally exactly-once delivery.
6. **Scoped qualification:** each qualified claim must name its adapter/platform, credential and policy boundary, threat cases and exact evidence. An unqualified private repo, Windows target, distributed deployment or SF-18 agent fleet is not implicitly supported.
7. **Read independently of effect authority:** expiry/revocation denies new writes, not automatically separately authenticated, read-only recovery inquiry. A new write/compensation requires a valid scoped grant.
8. **No reviewer barrier:** zero mandatory approving reviews is retained. Technical independence means separated policy and credential origins, not mandatory different humans.
9. **No orchestrator waiver:** SF-17/18 deferred; shared agent/fleet budget/lease controls SF-R10 remain **UNMET overall**. Manual serial reference profile may exclude that *capability* explicitly, but not relabel the product requirement passed.

## B. Evidence trust classification

| Evidence category | Producer and owner | Independent verifier / store | Accepted only if | Failure behavior |
| --- | --- | --- | --- | --- |
| Publisher attestation and trust roots | GitHub attestation provider + separately owned operator policy | PQ-01 pinned verifier external to candidate | Exact artifact digest and expected issuer/repo/workflow/event/ref/source plus verifier/root and trust epoch | Reject mismatch; report unavailable for stale offline proof without freshness |
| CI acceptance facts | Authenticated CI provider; expectations held separately | PQ-02 provider query under protected policy | Exact source/integration commit, run/attempt/event/workflow, required complete success and bound artifact | Reject mismatch/partial; provider outage is unavailable |
| Release grant | Independent operator or trusted bounded grant service | PQ-02 effect-boundary evaluator under protected policy | Specific artifact, environment/target, operation, effect, policy, epoch/expiry/revocation | Deny effect; leave read-only reconciliation possible |
| Artifact + SBOM + provenance | Controlled PQ-03 build job, retained bytes | PQ-03 independent digests/attestation policy | Exact source/build/tool identities and bytes match accepted grant and retention | No rebuild-on-promotion; missing stored bytes block |
| Intent/lease/receipt | PQ-04 disk ledger; PQ-05 destination | Transactional coordinator + authoritative destination status/fence | Stable operation identity and immutable intent, target-enforced generation, independently observed disposition | Unknown/contradictory does not trigger blind write |
| Live health/incident | PQ-06 authenticated collector and durable operator store | PQ-06 bound source/environment/epoch, ordered evidence, operator acknowledgement | Fresh, correctly scoped observations and verified recovery review | Unknown/stale, preserve incident unresolved |

Each evidence instance must be tamper-evidently bound to `schemaVersion`, `kind`, producer/issuer, stable identity, relevant policy digest/version, source and environment where applicable, observation/issuance time, evidence digest and exact failure/disposition state. A SHA-256 checksum detects changed bytes but does not authenticate who supplied the checksum. A locally supplied URL is not proof of a provider result.

## C. Prospective version-1 data identities (fields are requirements, not functioning APIs)

| Contract / owner | Minimum immutable fields or identity | Mandatory independent check | Disallowed shortcut |
| --- | --- | --- | --- |
| **PublisherTrustPolicy** / PQ-01 | policy ID+version+digest; trust-root/verifier digest; allowed repository numeric ID/name; signer/workflow identity, event/ref, source constraints; release epoch, expiry, maximum evidence age, downgrade policy | Operator-controlled copy outside archive; rooted verifier; intentional root rotation; artifact digest | Bundle self-supplies its verifier/policy or redefines allowable signer |
| **PublisherEvidence** / PQ-01 | artifact SHA-256, attestation/signature bytes and digest, issuer/signer/workflow ref, source SHA/tree, artifact ID, provenance parameters, verification time and provenance identifiers | Cryptographic verification **and** exact trust-policy match; offline freshness classification | Treat any valid signature or `publisher` string as authoritative |
| **ProviderCIReceipt** / PQ-02 | repository numeric ID, commit SHA, PR head/base or merge SHA, workflow identity/revision, run ID, attempt, event, named required jobs+provider IDs, conclusions, artifact SHA | Query provider independently; confirm jobs complete, no skips/neutral/cancelled failures; policy controlled outside candidate | Trust candidate JSON, a mutable check name, PR-stage result for different merge-group SHA |
| **EffectGrant** / PQ-02 | grant ID, principal/issuer identity, source/artifact digest, target+environment+adapter, exact effect allowlist, migration/recovery digests, policy digest/version, unique operation ID, issuance/expiry, revocation epoch | Check authenticated signature/credential or protected equivalent; recheck at real target effect; atomically prevent reuse where needed | Approval-pin or workflow string alone causes deployment |
| **RetainedBuild** / PQ-03 | release/version, exact immutable bytes+SHA, source commit/tree, build recipe/toolchain/action pin, SBOM/provenance+digest, storage location and retention policy | Download independently; rehash actual promoted bytes, check attestation and manifest linkage | Rebuild artifact from source at promotion |
| **OperationIntent** / PQ-04 | stable operation key, immutable source+artifact+destination+effect+grant digest, state, transactional monotonic generation/fence, retry attempt, timestamps, previous observed state | Durable transaction and idempotent identity; protect against old backup epoch; commit intent before send | A lease existing only in one coordinator process ensures remote fencing |
| **DestinationReceipt** / PQ-05 | target ID/environment, stable operation ID, enforced generation, effect identity/hash, authoritative status, target-observed revision/time | Query authenticated destination for exact ID/fence, distinguish unknown/contradiction | Interpret timeout, missing receipt or uncertain migration as no effect |
| **ObservationEvent** / PQ-06 | immutable event ID, source+target+environment+epoch, authenticated channel, observed/received time, domain/state, evidence digest, order/sequence | Authenticated source and freshness, replay/dedup/reorder checks | Offline `sf16` caller snapshot equals live health |
| **IncidentTransition** / PQ-06 | stable incident ID, triggering observation digest, append-only history, owner/runbook, acknowledgement identity, recovery evidence, transition time, disposition | Durable audit and operator-authorized close after verified recovery | Fresh healthy reading or missing past history auto-closes incident |

For schema implementations, use strictly versioned bounded validation: reject unknown security-critical fields, duplicate keys, unexpected identities and inconsistent time/fence; apply size/time/retry limits. Migration between schema versions must be explicit, tested and reversible or safely forward-recoverable. Do **not** add acceptance booleans to legacy fixture schemas as a way to turn old synthetic data into authority.

## D. Typed result states and allowed behavior

- `QUALIFIED` is claim-, adapter-, environment-, policy- and exact-candidate scoped; it is not a global factory switch.
- `REJECTED` is a verified policy violation (e.g., wrong signer/digest, revoked grant, stale fence). No dependent write.
- `UNAVAILABLE` means the required trust/provider/target evidence could not be obtained (e.g., network or policy freshness failure). Block dependent claim/effect, preserve safe independent work.
- `UNKNOWN` means a possible effect occurred but cannot be authoritatively classified. Persist intent; allow separately authorized read-only reconciliation and manual escalation; forbid unattended new write/compensation.
- `UNSUPPORTED` means the target/capability lacks required fencing/status/signature/private-repo entitlement. Reject unsupported unattended mode, do not emulate proof with local flags.
- `EXPIRED` is proof/grant freshness failure. Deny new effects; do not erase incident/operation history.
- `PENDING` and `NOT_STARTED` are progress labels, **never** pass statuses.

States are distinguished in storage and reports. Do not coerce errors, missing fields, previous passing candidates, or stale checks into `QUALIFIED`.

## E. Profile and capability matrix

| Profile/capability | Default intended coverage | Qualification requirement |
| --- | --- | --- |
| Public s-f factory publisher | PQ-01 GitHub artifact attestations; GitHub release controls | Exact signer/workflow/policy/root and supplied artifact; issuer trust and freshness |
| Private adopter repository | **UNSUPPORTED BY DEFAULT** by public-repo assumption | Probe actual GitHub account entitlement or independently approved alternative authenticated publisher |
| Single-host disposable Linux reference service | PQ-04/05/06 reference only | SQLite on local disk, enforced destination fence/idempotency, authenticated status/health, least-privilege grants |
| Windows as factory development host | Existing native hosted source tests, not a live PQ-05 target | Separate target qualification before any production deployment claim |
| Multi-host or shared-network-filesystem coordinator | **OUT OF SCOPE** | Dedicated transactional/fence-capable server store and separate failure/race campaign |
| Manual serial lifecycle | **IN SCOPE** for chosen reference | Bounded execution, output, retries, storage, serial work and explicit operator effects |
| Autonomous agent orchestration/shared fleet budget | **DEFERRED** (SF-17/18) | Full SF-R10 admission, shared budget, cancellation and lease tests before qualification |

Reference profile must define its actual Linux distribution/runtime, target adapter, command limits, health thresholds, retention policy and owner *before* live campaigns. Do not assign arbitrary measured performance or cost numbers now.

## F. Claim-by-claim acceptance and falsification oracle

| Claim and requirement | Owner/gate | Required counterexample (must be rejected) | Evidence type and owner |
| --- | --- | --- | --- |
| Publisher provenance, SF-R05 | PQ-01/PQ-07 | Right digest signed by wrong identity/workflow; replaced root; expired or downgraded release | Signed artifact bundle; independent verifier trace / trust-policy custodian |
| Exact-byte installation/upgrade, SF-R01–05,11 | PQ-01/PQ-07/PQ-08 | Changed member, pin/provenance substitution, dirty collision, foreign instruction loss | Protected fixture diff/installed-byte trace / installer owner |
| Real independent CI, SF-R07/12 | PQ-02/PQ-07 | Attempt/SHA/checker/event mismatch; skipped job; provider unreachable | Provider-backed expected-versus-observed run/job IDs / gate-policy custodian |
| Bound effect authorization, SF-R06–09 | PQ-02/PQ-05/PQ-07 | Candidate-approved or replayed/expired grant; policy changed before dispatch; wrong destination | Effect-boundary logs and authenticated grant / release authority owner |
| Artifact retention, SF-R05–07 | PQ-03/PQ-07 | Downloaded different digest, missing artifact, changed build-tool input, rebuilt promotion | Immutable bundle+manifest/SBOM/provenance / publisher custodian |
| Durable coordinator, SF-R06 | PQ-04/PQ-07 | Kill after send, competing worker, stale restored fence, DB write failure | SQLite state+cross-process crash/race trace / coordinator owner |
| Real target, SF-R06/12 | PQ-05/PQ-07 | Delayed expired lease, ambiguous receipt, unsupported atomic precondition, partial migration | Authenticated target status + observed effect count / target owner |
| Live observation/incident, SF-R06/07 | PQ-06/PQ-07 | Spoof/stale/truncated/reordered observations; restart; premature closure | Durable event/incident history + operator acknowledgement / operations owner |
| Bounded manual work, SF-R09/10 | PQ-00/PQ-07 | Denied release halts safe source review; unbounded retries/storage | Explicit manual profile contract, bounded execution tests / workflow owner |
| Shared agent budgets, SF-R10 | SF-18 **deferred** | Concurrent fleet cancellation/overspend not exercised | **UNMET overall**, no acceptance by manual exemption |

## G. Work-package activation prerequisites, owners and resource fields

- **PQ-01:** signer workflow exact file/revision; expected repo ID; initial verifier/tool hash and trusted root/policy custody; key/rotation owner; supported public/other entitlement.
- **PQ-02:** release-policy custodian, privileged provider query identity, immutable protected check-policy origin, grant issuer and effect executor, revocation/replay store and expected destination claims.
- **PQ-03:** verified pinned build inputs, retention destination/access/expiry, versioning, exact build recipe and SBOM format, source-to-artifact acceptance policy.
- **PQ-04:** single host and local durable directory; backup/restore owner; SQLite/runtime minimum; transactional migration and recovery runbook; binding to destination-enforced fence selected in PQ-05.
- **PQ-05:** expressly authorized disposable target/credential owner, isolated namespace, effect/health APIs, migration and compensation boundaries, destroy plan.
- **PQ-06:** authenticated health/event producer, trust channel and owner, incident store/access and resolution authority, retention policy.
- **PQ-07/08:** release candidate/dossier acceptance authority, observation duration/thresholds, resource measurements, publication authorization and separately authorized adopter/pilot.

Each future work order binds its own expected external effects and evidence: revision (commit/tree), action workflow/run/job/attempt/merge SHA, toolchain/runner versions, artifact digests, target/fence/operation/grant, time bounds and measured CI/deploy/storage/provider cost. A credible *operator-created* verification report is not a substitute for the authenticated provider raw facts it refers to.

## H. Review and amendment

At PQ-00 acceptance, inspect changes against the independent baseline and ensure no executable changes to `src/`, `tests/`, `.github/`, policy-setting APIs or any other repository. Retain historical SF-19 contracts and evidence. Following projects may adopt versioned implementations of the **prospective** schemas above after real compatibility/falsification tests. A future replacement of SQLite with server transactions becomes justified if a second independently active host is required; a different publisher verifier becomes justified if public attestation support or offline/privacy constraints cease to match the profile.

**No authority or product qualification is created by this document.**
