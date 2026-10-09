# PQ-07J — independent operator decision inventory (declarations only)

Parent: PR #47 at `10b6aebca2f9357648413d1c4d8a449de32dfff1`, tree `a233ba492546ebf8fbbea0013a9e0853e4b4dfad`.

Source-only readiness assessment for eight external prerequisites: independently controlled verifier/root, genuine publisher workflow identity, provider CI checkout, scoped grant issuer/revocation/replay, immutable artifact/provenance custody, real crash/restore and remote fence, authorized disposable Linux target, and authenticated live-operations owner/incident service.

The `inspect_external_decisions` API checks a separately supplied digest-pinned canonical input, exact source/tree/artifact and limited Linux test profile, then reports missing, proposed, pending, or blocked custody declarations. **There is intentionally no accepted `approved` field** because candidate-authored records cannot grant their own authenticity. Even complete declarations produce `custodyAuthenticated=false`, `externalEffectsAuthorized=false`, `productionQualified=false`, `publishAuthorized=false`, `adopterPilotAuthorized=false`. Operator identities, signer material, retention and environment authority must be validated outside the candidate by their controlling parties.

Tests cover missing inputs, complete but unauthenticated declarations, wrong source/platform, duplicate owner decisions, self-approved state, forged qualification and changed pinned manifest. This package does not create or accept real PQ-07 campaign evidence. PQ-08 and SF-R10 remain blocked.

Draft stacked PR #48; integration reserved for protected cumulative PR #50.
