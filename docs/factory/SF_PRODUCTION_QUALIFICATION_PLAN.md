# Software Factory — Production Qualification Implementation Plan

**Programme:** PQ-00 → PQ-08 · **Status:** PQ-07A–L source protected-integrated via PR #50; PQ-07M–R source qualification preparation through PR #56; live PQ-07/PQ-08 **BLOCKED** · **Date:** 9 October 2026 (EAT)  
**Repository:** `spsoftwarefc/s-f` · **Frozen starting baseline:** `45a1d78197667efeedf5f2e60ca07f1ff070a6f6` · **Tree:** `c498695eb49d6ca4af2859fa2164a85881020837`

This is the forward-looking implementation plan derived from the 9 October 2026 production qualification assessment. PQ package IDs are **not PR numbers**. Every package starts with a separately committed work order and is delivered as **one active PR at a time**. Each completed package must update its status using exact evidence. A PR being open or CI being green does not mean that its package has been accepted, merged, released or deployed.

## 1. Verified source starting point and release boundary

[PR #30](https://github.com/spsoftwarefc/s-f/pull/30) was protected-merged on 9 October 2026 at 00:16:50 EAT. At programme intake, `main` was `45a1d78197667efeedf5f2e60ca07f1ff070a6f6`, with no open PRs and only `main`. Existing [protected merge-group run 37845247779](https://github.com/spsoftwarefc/s-f/actions/runs/37845247779) was successful; the prior assessment reports 332 passing tests on each platform and successful dependent acceptance. The active ruleset requires GitHub-provider-bound Linux, Windows and `sf07-acceptance`, and a protected squash merge queue; it requires **zero approving reviewers**.

Current distribution is `s-factory 0.0.1` (development preview, Python >=3.12); `pyproject.toml` declares `setuptools>=68`, **not** a reproducible locked build environment. SF-13I exact-byte archive installation, SF-14 offline release planning, SF-15 in-memory simulated target and SF-16 offline operational classification are integrated development source; they **do not** supply authenticated publisher authority, independent release permission, disk durability, live deployment or verified incident resolution. Preserve SF-19 fixture fields `publisherAuthenticityVerified=false`, `externalReleaseAuthorityVerified=false`, `independentCIVerified=false`, `realDeploymentExercised=false`, `durableRecoveryVerified=false`, `liveOperationsVerified=false` and every other production authorization false. Do not rewrite fixture meanings to pass new gates.

**Separate scopes:** (A) factory release: authenticated, versioned and verifiable distribution plus installation/upgrade/removal; (B) adopter deployment: a *specific* project adapter, environment and artifact/credential/migration/health/recovery interface. A verified factory does not automatically qualify every adopter; a successful Linux reference service does not qualify Windows deployments, other providers, irreversible migrations or multi-host coordination.

## 2. Planned bounded sequence and acceptance

| Package | State as of initial plan | Deliverable | Acceptance gate and proof |
| --- | --- | --- | --- |
| **PQ-00** Scope/contracts | **INTEGRATED — [PR #31](https://github.com/spsoftwarefc/s-f/pull/31), contract only** | Frozen claim/requirements map; profile capability matrix; prospective evidence and authority identities; threat-model update; external decisions and resource budget | Independent preservation/authority review, complete requirement→owner→failure→evidence mapping, no false qualification, no code or gate weakening; protected PR checks still apply |
| **PQ-01** Publisher authentication | **PARTIAL SOURCE INTEGRATED — PQ-01A/B**; live qualification pending | First GitHub public-repo attestation verifier; independently controlled trust policy/verifier bootstrap; installer/upgrade/replay checks; retained signed evidence | Wrong digest, signer, repository, workflow, ref, source or substituted policy fail; expiry, rollback, unsupported or stale/offline trust statuses explicit; no candidate-supplied self-trust |
| **PQ-02** Independent provider and release authority | **PARTIAL SOURCE INTEGRATED**; external authority pending | Candidate-independent CI policy/provider verifier; scoped signed/authenticated release grant and consumer verification | Verify real run/attempt/head/base/integration SHA, event, required checks and artifact against protected expectations; reject forged/missing/skipped/cancelled/neutral/substituted runs, wrong destination, expired/replayed/revoked grant, policy TOCTOU |
| **PQ-03** Exact-byte build and retention | **PARTIAL SOURCE INTEGRATED**; signed provenance/immutable retention pending | Pinned build/toolchain and action inputs; retained signed artifact/provenance/SBOM/evidence manifest; build-once promotion | Independently retrieve/check bytes and digest; forbid rebuilding on promotion; substitution, missing retention, unpinned inputs and incompatible/unsigned provenance fail |
| **PQ-04** Durable coordination and recovery | **PARTIAL SOURCE INTEGRATED**; crash/restore qualification pending | Single-host SQLite transactional ledger; stable operation key; generations/fencing; transactional intent and idempotent reconciliation | Real process kills and competing processes; crash at each boundary; SQLite contention, I/O failure, restore and stale fence; uncertain effects not blindly retried |
| **PQ-05** Real reference deployment | **PARTIAL LOCAL TARGET SOURCE INTEGRATED**; real authorized service pending | Authorized disposable Linux reference service; least-privilege target connector, target-side fence/CAS, status/health/migration/compensation | Real failed deploy/health, lost reply, delayed worker and contradiction; target without authoritative fence/status is unsupported for unattended recovery; no other project affected |
| **PQ-06** Live operations | **PARTIAL LOCAL INCIDENT SOURCE INTEGRATED**; real authenticated live ops pending | Authenticated observations and durable incident journal; owner acknowledgements; recovery evidence/runbooks; bounded proposals | Replay/forgery/staleness/truncation detected; incident survives restart; no auto-close on recovered health or unauthenticated input |
| **PQ-07** Scoped production-qualification campaign | **PQ-07A–F SOURCE CANDIDATES**; authenticated live campaign not started | Retained release/installation/upgrade/remove and reference deploy/restart/recovery dossier | Every mandatory **in-scope** claim backed by exact source/attempt/policy/environment/evidence; explicit NOT QUALIFIED outside scope and SF-R10 disposition |
| **PQ-08** Authorized publication and adopter pilot | NOT STARTED | Versioned publication of accepted exact bytes; separately approved isolated adopter pilot | Published digest matches PQ-07 accepted bytes; authorized project-owned checks, rollback and observed pilot effects recorded; no automatic general deployment rights |

Serial execution order: `PQ-00 → PQ-01 → PQ-02 → PQ-03 → PQ-04 → PQ-05 → PQ-06 → PQ-07 → PQ-08`. Design spikes and targeted offline tests may be carried out inside an authorized package without widening its authority. Later packages require their predecessors' pertinent contracts, but **a missing live external prerequisite blocks only claims needing that prerequisite**, not independent source work. One work order/active PR at a time by default; no automatic merge cadence is implied.

### Distinct stage-gate dispositions

`specified` → `implementing` → `locally-verified` → `CI-verified` → `accepted-source` are *development* stages. Separately record `publisher-authenticated`, `release-authorized`, `artifact-retained`, `deployment-qualified`, `operations-qualified`, `production-qualified-for-profile`, `published`, `adopter-pilot-accepted`. **Unknown, unsupported, failed, unavailable and expired** are not synonyms for passing. Prior synthetic fixture success remains development-only, even after a protected merge.

## 3. Architecture and trust constraints

**PQ-01 publisher:** use GitHub artifact attestations for the current **public** `spsoftwarefc/s-f` publisher, subject to exact supported repository/plan capability. Do not silently require the same for **private adopter** repositories: GitHub's private/internal attestation feature is Enterprise Cloud-gated. A separately approved private/offline provider (for example, managed-key Cosign with qualified key custody) is a future adapter, not a PQ-01 promise. Independently provision verifier version/digest, source-repo ID, expected workflow identity/ref, accepted signer, roots/policy digest, maximum evidence age, artifact digest and update epoch. A candidate archive must not bring its own acceptance trust. Offline attestation proof cannot establish current revocation/freshness indefinitely. A signature from an unexpected workflow is rejection, not permission.

**PQ-02 authority:** independently obtain GitHub/provider run metadata from the trusted provider; bind repository ID, workflow ID/path and trusted revision, PR/head/base or merge-group SHA, exact run ID/attempt/event, final required job conclusions and artifact SHA to candidate-independent expectations. Candidate-supplied URLs/JSON are leads, not authority. Create a grant independently of the candidate that binds principal, operation/grant ID, destination/environment, artifact digest, effect allowlist, migration/recovery and policy digests, expiry/revocation and replay scope. Verify **at the external effect boundary**; OIDC is acceptable only when the destination validates the necessary claims/policy. Independent technical release policy does **not** impose a second human reviewer.

**PQ-03 build:** pin runtime, action and build-tool dependencies (including exact setuptools tooling) before a reproducibility claim. Produce a stable artifact once and retain exact published bytes with digest, source, build inputs, provenance/SBOM/evidence identities and policy/version. Promotion must fetch and verify retained bytes, not rebuild from a tag. Define retention owner, location and expiry before qualification.

**PQ-04 recovery:** use SQLite on **local host storage**, `journal_mode=WAL`, `synchronous=FULL`, bounded busy handling, explicit write transactions and verified backup/restore. WAL is **not** a distributed coordinator and is unsuitable for an NFS-style shared WAL database. Persist stable operation ID and immutable intent before effect; reserve generation/epoch transactionally; prevent late/stale dispatch at the **destination** with fencing or equivalent atomic CAS. Lease expiry alone does not fence in-flight effects. Retry only after authoritative status/idempotency proof. Process death is tested separately from unclaimed power-loss guarantees. Backup restoration must not re-enable stale generations.

**PQ-05 reference:** begin with one isolated disposable Linux service; no paid or production VPS infrastructure is assumed. Qualified credentials must be least-privileged and destination-scoped, no secret retained in candidate evidence. Read-only authenticated reconciliation can continue under a separate authorization after a write grant expires; no write, compensation, migration or release without fresh effect authority. A target lacking atomic preconditions/idempotency/reconciliation must remain manually blocked.

**PQ-06 operations:** observations are authenticated and source/destination/epoch bound; a durable incident history survives crash/restart, preserves unresolved anomalies and requires authenticated manual resolution with independent recovery evidence. Missing, stale or contradictory observations are not healthy. Reuse existing adopter observability; no mandatory always-on server, collector, dashboard, notification provider or model API.

All adapters must avoid trusting user prompts, PR description, source changes, candidate logs, passed tests alone or locally generated checksums as an authority grant.

## 4. Requirement/claim ownership

| Requirement | Production-qualification owner | What must be demonstrated |
| --- | --- | --- |
| SF-R01–04 | PQ-01, PQ-07 and adopter-specific PQ-08 | Authenticated installation/upgrade/removal preserves target instructions, CI, existing files; qualified portability per selected profiles |
| SF-R05 | PQ-01, PQ-03, PQ-07 | Authenticated publisher and independent trust custody + exact retained distribution bytes |
| SF-R06 | PQ-02–PQ-07 | CI→grant→artifact→real effect→durable recovery→live observation with authentic evidence and scoped permission |
| SF-R07 | PQ-02, PQ-03, PQ-06, PQ-07 | Independently checked provider/release/operation/observation facts, not assertions |
| SF-R08–09 | PQ-00 and each gate | No new mandatory human reviewer; security-denied effects do not block independent work |
| SF-R10 | DEFERRED SF-18 (PQ-00 profiles, bounded command constraints) | Overall **UNMET** for agent shared budgets/leases; manual reference profile can explicitly exclude those claims but cannot mark SF-R10 passed |
| SF-R11–12 | PQ-00, PQ-07, PQ-08 | Installation never implies release; unsupported controls and unavailable evidence explicitly reported |

The stronger typed prospective contract and negative-case oracle is `docs/factory/PQ00_CONTRACTS.md`. Existing `docs/product/REQUIREMENTS.md` remains the canonical product requirements, not the plan itself.

## 5. Failure and recovery campaign

| Boundary | Mandatory adversarial cases |
| --- | --- |
| Supply chain | Correct digest/wrong publisher; right repo/wrong workflow/ref; replaced trust policy or verifier; policy expiry; signed old release and downgrade; valid old offline proof with unavailable online freshness |
| CI and permission | Wrong SHA/repo/attempt/merge-group; job skipped/neutral/cancelled/partly missing; candidate-modified check policy; provider outage; grant wrong effect/environment, expired/revoked/replayed/changed since plan |
| Artifacts | Absent retention; nonmatching download; source after build, provenance substitution; manifest/SBOM mismatches; rebuild substituted for promotion |
| Persistence | Death before/after intent, after send before receipt, after effect, before health; concurrent workers; full/locked/corrupt DB; schema migration; stale backup/fence |
| Live target | Delayed stale worker, duplicate operation, network timeout with possible effect, unsupported target CAS, contradictory receipt, migration partial/irreversible, compensation ambiguous |
| Operations | Forged/replayed/out-of-order/stale/future telemetry, truncated incident history, restarts, healthy signal after unreviewed anomaly |
| Adopter | Dirty/partially installed target, unrelated-owned files, unsupported platform/backend, modified instructions/CI, mixed trust contexts |

No end-to-end **exactly-once delivery** guarantee. Describe at-most-once external side effects only where the target actually enforces the property; otherwise uncertain outcomes block unattended retries. The release dossier must distinguish negative evidence, observations and estimates.

## 6. Activation decisions and finite resources

Unresolved external decisions (do not invent or preauthorize): trust-policy custody and verifier bootstrap/version hashes; precise signer/workflow identity; public/private adopter capabilities; destination credential owner; disposable target; immutable artifact/evidence retention; observability/operator and incident runbook; any incremental paid budget. Each decision must be documented and independently accepted before its first real effect.

Preserve the repository's normal required PR-stage native Linux/Windows and dependent `sf07-acceptance` and the separately enforced protected `merge_group` on actual queue identity. Use focused local checks during editing and applicable local final acceptance once per stable candidate. Do not launch redundant push workflows or rerun unchanged evidence. Record exact run/job IDs, attempt and tested SHA when checks actually occur. If merge is not yet authorized, stop after a reviewable PR—do not simulate the merge. No self-hosted CI on a production VPS by default.

Resource ledger for each package: measured CI minutes (by run), local test wall time, artifact/evidence bytes and retention, deployment/recovery time, observed external/provider/model costs, failures/retries and their causes. No unmeasured cost, test count or delivery date is promised. Choose live health thresholds and observation duration **before** the PQ-05/PQ-07 experiment and document their rationale, not afterward.

**SF-17 and SF-18** (agent host/orchestration) remain deferred. No arbitrary code/model-worker admission limit is added to the manual reference lifecycle. Maintain existing bounded command duration, output, retry, disk and serial work constraints. If shared fleet budget/cancellation becomes an adopter release requirement, implement and qualify it separately before making that claim.

## 7. PQ-00 delivery and next handoff

PQ-00 work order: `docs/factory/work-orders/PQ-00.json`. Contract: `docs/factory/PQ00_CONTRACTS.md`. Candidate evidence: `docs/factory/evidence/PQ-00.md`. Scope limited to those three paths, this plan, `README.md`, `docs/factory/PROJECT.md`, `docs/product/REQUIREMENTS.md` and `docs/product/THREAT_MODEL.md`; no source, test, Actions, settings, release or deployment changes.

**PQ-00 exit** requires: source-bound work-order-first history; bounded plan and coverage map; prospectively versioned artifact/CI/grant/ledger/incident contracts, threat counterexamples, known unresolved decisions; an honest scope/preservation review; and required hosted gates when PR is integrated. **It is not production qualification.** Next substantive implementation is PQ-01 only after PQ-00 contract review; choose precise verifier/action dependencies and target capability from independently controlled source.

## 8. Primary references

- [Existing product requirements](../product/REQUIREMENTS.md), [threat model](../product/THREAT_MODEL.md), [SF-19 fixture limitations](SF19_QUALIFICATION.md), [project rules](PROJECT.md), [work-order contract](WORK_ORDER.md).
- [GitHub artifact attestations](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations), [GitHub OIDC claims](https://docs.github.com/en/actions/reference/security/oidc), [SLSA 1.2 artifact verification](https://slsa.dev/spec/v1.2/verifying-artifacts).
- [Sigstore Cosign](https://docs.sigstore.dev/cosign/verifying/verify/), [SQLite WAL](https://www.sqlite.org/wal.html), [SQLite synchronous PRAGMA](https://sqlite.org/pragma.html#pragma_synchronous), [TUF specification](https://theupdateframework.github.io/specification/v1.0.36/), [OpenTelemetry collector security](https://opentelemetry.io/docs/security/config-best-practices/).

**Important:** referenced standards inform the design; they do not certify the implementation, and this document grants no authority to publish or deploy.
 
## 9. Execution reconciliation — PQ-00 integration and PQ-01A

- **PQ-00 source integration completed:** [PR #31](https://github.com/spsoftwarefc/s-f/pull/31) protected squash-merged on **9 October 2026 at 06:25:03 UTC**, `main` SHA `09d5346c628560e7e33f947a8b08b44960cef14f` (tree `da32ea87b5c675d88436ffc517e51e78b34be609`). Required PR-stage and separate [merge-group run 37893122459](https://github.com/spsoftwarefc/s-f/actions/runs/37893122459) (Linux, Windows, sf07-acceptance) succeeded. This qualifies PQ-00 **contract/source incorporation only**.
- **PQ-01 split for bounded delivery:** PQ-01A read-only operator-pinned public GitHub attestation verifier; PQ-01B authenticated installer/upgrade effect binding, independently provisioned real policy and signed-evidence live qualification. See [PQ-01A work order](work-orders/PQ-01A.json) and [publisher adapter specification](PQ01_PUBLISHER.md).
- **PQ-01 overall remains IN PROGRESS and not qualified.** PQ-01A success alone cannot satisfy PQ-01 acceptance, publisher custody or installer trust. No real signing, artifact publication, new environment credential, installation, deployment or SF-R10 admission was performed.

## 10. Protected PR #38 source integration and PQ-07A next gate

On 9 October 2026 at 07:14:13 UTC, [cumulative PR #38](https://github.com/spsoftwarefc/s-f/pull/38) protected squash-merged PQ-01B through PQ-06 **partial source implementations** into `main` as `766509f380b901a8672d7ee7b2137ef28a234685` (tree `dad41cd34963d3b30a05338cb6ebd7798cc2725b`). Exact-head [PR run 37897202944](https://github.com/spsoftwarefc/s-f/actions/runs/37897202944) passed 376 tests on each of Linux and Windows and `sf07-acceptance`; separate [merge-group run 37897557665](https://github.com/spsoftwarefc/s-f/actions/runs/37897557665) passed the protected group checks on final main SHA. Lower stack PRs #33–#37 were closed as incorporated without independent merges. This is **development source acceptance only**.

Source components now include opt-in publisher-to-installer exact-byte bridge (PQ-01B), pinned CI policy/HMAC reference grant observations (PQ-02), local retained artifact store (PQ-03), durable SQLite uncertain-intent ledger (PQ-04), local target-side CAS/receipt simulation (PQ-05), and local authenticated-reference incident journal (PQ-06). Each is bounded, with declared unqualified external proof/effect dependencies. They do **not** establish independent key/policy custody, genuine signed release/artifact, durable replay/revocation, authenticated live target/incident operations, cross-process crash/restore qualification or production publication.

PQ-07A is a **read-only dossier gap assessment**, not the PQ-07 live qualification campaign. Its work-order and evidence paths are [PQ-07A](work-orders/PQ-07A.json) and [PQ-07A evidence](evidence/PQ-07A.md). Production qualification, external release authority, PQ-08 publication/pilot and SF-R10 overall remain BLOCKED/UNMET. A new protected merge for PQ-07A requires a separately stated cadence/authorization; no action here grants it.

## 11. PQ-07A–F source-candidate stack and next protected integration

After [PR #38](https://github.com/spsoftwarefc/s-f/pull/38) protected-integrated partial PQ-01B–PQ-06 source, implementation continues as a bounded and **still non-qualifying** PQ-07 source campaign:
- [PR #39](https://github.com/spsoftwarefc/s-f/pull/39): PQ-07A structural evidence dossier and post-PR38 source reconciliation.
- [PR #40](https://github.com/spsoftwarefc/s-f/pull/40): PQ-07B out-of-band policy digest, exact candidate/profile and epoch checks.
- [PR #41](https://github.com/spsoftwarefc/s-f/pull/41): PQ-07C abrupt process-death tests and read-only cross-store local reconciliation.
- [PR #42](https://github.com/spsoftwarefc/s-f/pull/42): PQ-07D exact local retained archive, manifest, SBOM/provenance and build lock digest audit.
- [PR #43](https://github.com/spsoftwarefc/s-f/pull/43): PQ-07E bounded SQLite evidence log with local hash chaining and negative-case presence.
- [PR #44](https://github.com/spsoftwarefc/s-f/pull/44): PQ-07F cross-package fail-closed qualification preflight.

These were **development candidate** PRs. The user-selected merge checkpoint **PR #44** was completed by a protected squash merge on 9 October 2026 at commit `5d042208a148f9b75a429b11c8fe63f1ccef65d0` (tree `c595fe547147edfd0d0bd7ef158778d4d680ff53`). The lower stacked PRs were closed as incorporated and not separately merged. The cumulative PR #44 was targeted to protected `main` and integrated only after required hosted checks and separate GitHub `merge_group` validation; the lower superseded PRs were subsequently closed as incorporated. Do not bypass rules, direct-merge, or rerun unchanged checks. The merge-queue operator must preserve the required SQUASH method.

A completed local dossier, local signed-byte *checksum*, process-death test or local SQLite hash chain **never authenticates producer authority**. Genuine provider-issued attestations, independently protected release grant and policy, durable replay/revocation custody, an authorized running Linux reference target, migration/health/compensation and operator-confirmed live incidents remain PQ-07 mandatory **NOT QUALIFIED**. PQ-08 publication and adopter pilot remain **NOT STARTED/BLOCKED**. No new paid service, worker fleet, reviewer requirement or production VPS use is authorized. SF-R10 remains **UNMET overall** until independently implemented and qualified in SF-18 or equivalent.

## 12. Protected PR #44 source merge and PQ-07G–L no-go preparation (PRs #45–#50)

[PR #44](https://github.com/spsoftwarefc/s-f/pull/44) protected-integrated PQ-07A–F source on **9 October 2026** as `5d042208a148f9b75a429b11c8fe63f1ccef65d0` (tree `c595fe547147edfd0d0bd7ef158778d4d680ff53`). Protected incorporation is development-source integration, **not** externally authenticated PQ-07 production acceptance.

The user-set next protected merge checkpoint is **PR #50**, with bounded draft stack work orders and source-only outputs:

| PR | Work order | New source-only capability |
| --- | --- | --- |
| [#45](https://github.com/spsoftwarefc/s-f/pull/45) | [PQ-07G](work-orders/PQ-07G.json) | Exact-candidate, operator-digest-pinned raw positive/negative proof-byte gap intake |
| [#46](https://github.com/spsoftwarefc/s-f/pull/46) | [PQ-07H](work-orders/PQ-07H.json) | Strict PQ-07G/PQ-07F cross-evidence no-go preflight join |
| [#47](https://github.com/spsoftwarefc/s-f/pull/47) | [PQ-07I](work-orders/PQ-07I.json) | Read-only operator CLI for evidence inventory |
| [#48](https://github.com/spsoftwarefc/s-f/pull/48) | [PQ-07J](work-orders/PQ-07J.json) | Eight distinct external trust/deployment/operational custody decisions, declarations only |
| [#49](https://github.com/spsoftwarefc/s-f/pull/49) | [PQ-07K](work-orders/PQ-07K.json) | Combined adversarial false-green campaign regression |
| [#50](https://github.com/spsoftwarefc/s-f/pull/50) | [PQ-07L](work-orders/PQ-07L.json) | Cumulative source-only documentation/reconciliation and protected integration checkpoint |

PRs #45–#49 are not individually mergeable integration targets: cumulative PR #50 must pass exact-head hosted Linux/Windows/`sf07-acceptance` and separate protected `merge_group` checks before merge. No reviewer request or paid infrastructure is introduced.

**Unchanged release boundary:** no candidate-supplied manifest, issuer label, local SQLite chain, locally rehashed bytes, fully declared custody inventory or successful source test can authenticate an independent publisher, provider, policy custodian, effect grant/revocation, retained immutable build or real fenced target. The **independently authenticated live PQ-07 campaign has not been conducted**. Operator-supplied verified trust/verifier roots, actual signed provenance and CI/effect evidence, approved disposable Linux service with remote fence/recovery, live telemetry and human-owned incident evidence remain **required before PQ-07 is eligible for external acceptance**. PQ-08 publication/pilot remains separately authorized and **NOT STARTED**; SF-R10 overall **UNMET**.

Any actual live campaign must be initiated under a separate bounded operator work order naming the independent custodians, validated artifact/policy, exact runner/attempt/environment and authorized external effects. This source integration authorizes none of them.

## 13. Protected PR #50 integration and independently owned live qualification handoff

[PR #50](https://github.com/spsoftwarefc/s-f/pull/50) was protected squash-merged on **9 October 2026 at 09:05:58 UTC** as `0a59eb0078826530493db0c2a0211470d9368a8d` (tree `b36a0b92793c754dc55dd102441461b3accdee22`). Required [merge-group run 37908722988](https://github.com/spsoftwarefc/s-f/actions/runs/37908722988) passed Linux, Windows and `sf07-acceptance`. PRs #45–49 were closed as incorporated (not individually merged). Source readiness PQ-07A–L does **not** establish an independent signer, grant, retained build, live target, or authenticated operator.

The next user-selected protected source integration checkpoint is **PR #56**. PRs #51–55 are sequential source work and must not be individually merged. The active handoff is [PQ-07M external activation contract](PQ07_EXTERNAL_ACTIVATION.md) and its work order. The next packages prepare a **manual-only** publisher attestation workflow, independently pinned provider/grant review, exact-byte retained-artifact consumption, and reference qualification procedures. All external effect execution remains independently blocked until the activation contract is met.

**Release disposition stays NO-GO:** real authenticated PQ-07 not conducted; PQ-08 publication/adopter pilot not started; SF-R10 remains unmet overall. A green PR or merge-group is necessary source validation, never a substitute for independent live acceptance. No hosted qualification workflow may automatically publish or deploy.

## 14. PQ-07M–R source implementation: protected checkpoint PR #56

User-approved sequence starts from [protected PR #50](https://github.com/spsoftwarefc/s-f/pull/50) integrated source identity `0a59eb0078826530493db0c2a0211470d9368a8d`. One development work order was committed **before** implementation for each package; the five lower PRs remain draft and must not be separately merged.

| Draft PR | Package | Exact new source capability | Excluded external claims |
| --- | --- | --- | --- |
| [#51](https://github.com/spsoftwarefc/s-f/pull/51) | PQ-07M | Real PR50 reconciliation and [external activation contract](PQ07_EXTERNAL_ACTIVATION.md) | No independent policy/root/target approval |
| [#52](https://github.com/spsoftwarefc/s-f/pull/52) | PQ-07N | **Manual-only** GitHub public preview wheel provenance workflow with commit-pinned actions and regression test | No workflow dispatched, no release or reproducible-build proof |
| [#53](https://github.com/spsoftwarefc/s-f/pull/53) | PQ-07O | Read-only operator-pinned provider CI review command with fail-closed dispositions | Metadata observation is not a grant or checkout attestation |
| [#54](https://github.com/spsoftwarefc/s-f/pull/54) | PQ-07P | Retained artifact exact-byte private copy checked by existing publisher verifier plus adversarial tests | Local store is not independent immutable custody |
| [#55](https://github.com/spsoftwarefc/s-f/pull/55) | PQ-07Q | Isolated child process exit, reopened local SQLite target CAS/fencing and [live-reference runbook](PQ07_REFERENCE_RUNBOOK.md) | No real remote service, migrations, health or incidents |
| [#56](https://github.com/spsoftwarefc/s-f/pull/56) | PQ-07R | This cumulative review, work-order and evidence reconciliation; solely protected merge candidate to `main` | No PQ-07 or PQ-08 product release acceptance |

The required Linux and Windows jobs, dependent `sf07-acceptance` and **separate protected `merge_group` check** determine source integration. Record observed run/job IDs and final merge SHA only after GitHub confirms them. Do not bypass the protected queue or directly merge lower PRs. Close lower PRs administratively only after protected PR #56 incorporation.

Even if the source stack is accepted: actual independent publisher/release trust, signed immutable provenance and artifact custody, authoritative CI/grant replay/revocation, real disposable Linux remote fencing/rollback and authenticated live incident evidence remain **unproven**. An opt-in preview signing workflow is not a production release; no workflow dispatch is authorized by source merge. Live PQ-07 **BLOCKED**, PQ-08 **NOT STARTED**, SF-R10 overall **UNMET**.
