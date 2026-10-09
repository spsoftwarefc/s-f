# PQ-07 — authorized disposable Linux qualification runbook (PQ-07Q)

**State:** NOT EXECUTED. This is the prospective, operator-gated procedure, not authorization for a VPS or adopter deployment. Local SQLite source tests do not satisfy remote-service claims.

## Preflight: must be independently accepted before the first real effect

1. Operator names the **disposable**, isolated Linux target and owner; documents least-privilege credential custodian, permitted effect operations, resource/network budget and termination/cleanup boundary. Production services and unrelated repositories explicitly excluded.
2. Verify exact qualified source/tree, release artifact digest, SLSA attestation subject/signer workflow+revision and verifier/root policy hashes from a source other than the release candidate. Obtain fresh trusted GitHub provider run/attempt/checkout and required jobs; do not use candidate-provided URLs or logs as authority.
3. Verify independently issued grant, scope/environment, expiry, revocation epoch, replay fence and destination-side enforcement. Manual-serial reference profile; multi-host/shared-budget SF-R10 not included.
4. Retain immutable single-built bytes, digests and complete SBOM/provenance; decide retention owner/location/expiry and rollback model *before* the exercise.
5. Freeze expected health probe, migration/compensation boundary, observation freshness and acceptance duration, and audit operator identities **before** observing outcomes.

## Execute only with a separate signed or independently held operator work order

| Scenario | Mandatory observed proof | Fail-closed result |
| --- | --- | --- |
| Install exact retained factory bytes, upgrade and remove | Pinned archive and before/after target-file preservation proof | Wrong bytes / changed unrelated instructions block |
| Prepare effect, kill process before dispatch | Durable intent, no remote effect | No blind dispatch on restart |
| Kill worker after remote CAS before receipt | Remote authoritative status and receipt correlated to operation/generation | UNKNOWN effect blocks unattended retry |
| Competing/stale worker after lease expiry | **Destination** atomically rejects old generation and conflicting idempotency key | A host-side lease alone is not a fence |
| Local ledger lock/full/corruption and verified backup restore | Recovery ledger and higher-generation fencing survive restart | Stale backup cannot reactivate old generation |
| Migration partially applied, failed health, compensation timeout | Authenticated target state/status and safe operator decision | Unsafe/irreversible compensation requires manual approval |
| Duplicate/delayed/out-of-order response | Idempotent remote receipt from authenticated endpoint | Contradiction blocks release |
| Forged, stale, replayed or missing health observation | Authenticated source/destination/epoch/freshness and incident journal | Missing/contradictory health is unknown |
| Restart with unresolved incident | Durable record and independently authenticated operator resolution | Healthy new signal cannot auto-resolve prior incident |

Retain positive and deliberately invalid negative artifacts, exact run/attempt/candidate and immutable storage references. Sign-off must distinguish local process death, real process kill and power-loss. Do not infer unsupported platforms, hosts, backends or capabilities from one Linux reference.

**After local package #55:** no service or remote credentials created. Only separately authorized real PQ-07 execution can change external readiness. PQ-08 publication/adopter pilot needs an additional independent approval.
