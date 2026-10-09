# PQ-07B — independently pinned qualification policy intake (candidate)

PQ-07B adds a strict read-only reference policy parser. An operator supplies the SHA-256 of a canonical policy through an external channel, together with a minimum policy epoch. The adapter rejects changed bytes, rollback, expiry, unknown fields, changed mandatory claim inventory and exact candidate/profile mismatches before reporting source scope agreement.

**Not authenticated custody.** The caller could still supply a malicious policy and its own digest. The assessor cannot establish the custodian, signing identity, online revocation, source authenticity, artifact signatures or any live effect. The output always reports `independentPolicyCustodyVerified=false`, `releaseAuthorized=false`, `productionQualified=false`.

Tests cover correct scope without release authority, modified policy, wrong pin, changed source, epoch rollback, expiry, altered claim oracle and unknown/duplicate fields. No live publisher or target was queried; CI run identities are recorded only after observed checks.
