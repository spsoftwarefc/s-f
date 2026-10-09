# PQ-07H — source-only PQ-07F/PQ-07G report join

**Parent:** stacked PR #45 `ef3b66e89ed7eeeb271f386f8ca2447ae5571657`, tree `c659e425201ea4ea7fd05fcf31050c50bfee6db5`.

The optional `raw_campaign` argument to `assess_preflight` binds the frozen PQ-07G raw proof inventory to the exact PQ-07F source commit, tree, artifact and independently supplied policy digest. It checks every frozen claim, positive and negative state, summary consistency, manifest digest syntax and all authority flags. Absence means `rawCampaignCasesPresent=false`. Complete local coverage means only locally observed raw-byte presence.

This join is intentionally source-only, side-effect-free, backward compatible with preflight callers and **always denies production qualification, release, publication and adopter pilot**. Candidate-controlled report bytes do not authenticate their issuer. The requirement for an external release trust custodian, real CI, effect grant, retained artifact, real fenced reference service, and live operator evidence is unchanged. SF-R10 remains unmet.

Tests: absent raw inventory, full-but-untrusted inventory, wrong policy/tree, missing case with false summary, duplicate claim, forged status and authentication flags. Hosted evidence not claimed until verified.

**Disposition:** draft stacked package pending cumulative protected PR #50; no actual live PQ-07 qualification or PQ-08 effects.
