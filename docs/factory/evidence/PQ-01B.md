# PQ-01B — exact-byte publisher apply boundary

Status: **SOURCE CANDIDATE ONLY**. The independently provisioned real GH verifier, trusted root, signer workflow, live signed attestation, operator-protected release epoch and verified recovery permissions have not been supplied. A fixture/mocked adapter cannot qualify the publisher.

The optional Python `sf.publisher_effect.authenticated_apply` API runs PQ-01A verification before a pinned filesystem apply, verifies that the subsequently read bytes match the observed artifact digest, then supplies the installer an isolated, byte-identical copy. It refuses removal and leaves `releaseQualified`, `productionQualified`, and `independentPolicyCustodyVerified` false. Existing CLI operations, preview behavior, and original SF-13–19 fixture semantics are unchanged.

Unit tests cover verified-copy routing, changed bytes between verification and apply, rejected evidence/authority confusion, wrong mode, and propagated filesystem failures. **Test execution, provider status and installed effects have not been measured yet.** No real installation or external effect is authorized by this PR. Remaining PQ-01B live and recovery qualification is blocked on independent trust custody and real verifier evidence.
