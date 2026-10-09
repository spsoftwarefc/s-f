# PQ-07 — Independent external activation contract (PQ-07M)

**Status:** frozen source handoff; no owner has been authenticated by this repository; no live campaign or real external effects authorized.

**Protected candidate baseline:** PR #50 merge `0a59eb0078826530493db0c2a0211470d9368a8d`, tree `b36a0b92793c754dc55dd102441461b3accdee22`, source-only Linux/Windows/acceptance merge-group run 37908722988. A future campaign MUST pin its **own** later release commit, tree, bytes, workflow/ref, policy epoch and full integration SHA; this baseline is not a release candidate.

## Operator-held declarations that cannot originate from candidate output

| Independent custodian | Mandatory independently verified binding | Blocked absent proof |
| --- | --- | --- |
| Publisher trust-policy owner | Separate approved policy/root hash and custody record, signer repo ID, workflow path/ref, SHA, expiry, minimum release epoch, pinned verifier executable/version/hash | Authenticate or install production bytes |
| Protected CI/release owner | Fresh provider-fetched run ID/attempt/event, exact source + merge-group identities, required final checks, protected workflow and artifact SHA | Grant or effect authorization |
| Grant issuer/revocation owner | Unique operation/grant IDs, principal, effect, target, artifact, policy epoch, expiry, authenticated replay/revocation ledger, destination enforcement | Any real effect or automatic retry |
| Artifact-retention owner | Exact once-built artifact bytes plus signed provenance and SBOM digests, independent retention location/access/expiry, no rebuild-on-promotion | Release distribution |
| Disposable target owner | Explicit isolated Linux service ID, purpose-scoped credentials, atomic target-side generation/CAS and status, backup/rollback boundaries | Live deployment, migration or compensation |
| Operations/incident owner | Authenticated observer identity, max age, incident journal retention, owner acknowledgements and independently observed recovery | Live operational acceptance |
| Publication/adopter owner | Separate PQ-08 permit, profile, rollback and observer for adopter-owned changes | Publication or adopter pilot |

Each authority may be the same human operator acting through separately controlled resources, but no candidate manifest, passing test, local HMAC, PR comment, or source file can certify its own independence. Required policy/identity values are supplied **out of band** with trusted custody; defaults are never accepted as authorization.

## Campaign gates (in order)

1. Freeze exact source commit/tree, release profile, signed policy hash, verifier, locked toolchain and immutable artifact digest in a signed or independently held campaign record; reject stale or substituted identities.
2. Prove genuine GitHub public-repo provenance (expected workflow ID/ref, source, subject digest), independent provider CI and replay-safe scoped release permission. The normal PR CI run does not itself authorize publication.
3. Retrieve retained bytes from the independently approved store, rehash, verify provenance/SBOM and authenticate the **consumed** installation bytes. Reject missing retention or package rebuild.
4. On a separately authorized disposable single-host Linux target, demonstrate pre-effect ledger commit, atomic remote fencing/CAS, idempotency, lost reply, process kill, stale worker, SQLite contention, restore from backup, migration/rollback and health. Record ambiguous outcomes as blocked; never blind retry.
5. Authenticate telemetry/incident events from that target, verify ordering, truncation, replay, freshness and operator-owned recovery. A healthy new observation does not auto-close unresolved incidents.
6. Run exact-candidate positive and deliberately false/forged/replayed/stale negative cases across the full PQ-07 claim oracle; obtain independent operator acceptance for the **named profile only**. Keep `SF-R10=UNMET` outside the manual-serial reference claim.
7. Even if PQ-07 is accepted, **separately** authorize PQ-08 publication, immutable identical-byte promotion and isolated adopter pilot. Neither follows automatically.

## No-go, budget and operational constraints

- No secrets in repository, PRs, logs, command arguments or evidence bundles. No self-hosted CI on a production VPS, paid service, automatic release or target-project edits as part of this source implementation.
- One PR actively implemented at a time; PRs #51–55 stacked on their predecessor and source merged only through protected cumulative PR #56. Work order must precede code. Run focused local tests first; retain exact-hosted SHA/run/attempt evidence; do not rerun green jobs merely for presentation.
- Public publisher attestation capability does not imply private adopter attestation availability. Unsupported host/platform claims are explicit and block only their respective profile.
- No claim of production qualification, publication or SF-R10 satisfaction without its genuine evidence. No operator names, artifact digests, costs or target credentials are invented here.
