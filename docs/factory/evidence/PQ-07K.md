# PQ-07K — adversarial cross-boundary source campaign

**Parent:** draft PR #48 commit `bdbd1e8adb70fedb7729117b36af7e97ece5cf4e`, tree `ea763b6c39f61bd30b181aa5098010b7542fef06`.

This package exercises the real source APIs together under independently specified fixture digests: all eight positive/negative raw proof bytes, declarations for every external custodian, and a structurally complete PQ-07F local preflight. The full synthetic test must **still** return `productionQualified=false`, `publishAuthorized=false`, `adopterPilotAuthorized=false`; declaration labels never confer trust, and SF-R10 remains UNMET overall. Cross-artifact substitution and self-asserted external approval are rejected.

This is *adversarial regression evidence for a deliberately unqualified source candidate*, not live GitHub issuer verification, independent immutable retention, real fenced target recovery or authenticated operator action. The tests have no credentials, network, publication, installation or deployment permissions.

The PR #45–49 draft stack is subject to cumulative protected integration at PR #50 only. PQ-07 live campaign and PQ-08 live release/pilot effects remain **NOT STARTED/BLOCKED** pending separately authenticated evidence and independent authorization. Actual run results must be recorded only after observed.
