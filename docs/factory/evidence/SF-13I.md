# SF-13I — Verified archive/lock binding to lifecycle (implementation candidate)

Baseline: post-merge reconciliation branch `sf23/post-merge-reconciliation` SHA `95ffa63ac79857f72d56a21376e8c851bac33801`, tree `bf1cb51a1022fd5339a1244d9668f73b9e29cfe9`. Work order `docs/factory/work-orders/SF-13I.json` was separately committed before implementation, at `b2d44d356ed46ec35548ac501730635b4734a55d`.

## Implemented so far

- `src/sf/distribution.py`: validate strict canonical installation lock against an independently approved trust pin and a completely reverified bundle.
- `src/sf/lifecycle.py`: optional proof on read-only plan, exact saved-plan apply and interrupted transaction recovery, with immutable lock identity stored in plan/journal.
- `src/sf/cli.py`: expose bundled proof arguments for integrate/upgrade/recover.
- `tests/test_distribution.py`: negative fixtures for absent/tampered/noncanonical/stale/expired lock and proof binding across apply and recovery.

## Acceptance status and limitations

**Not locally or CI verified at dossier creation. Not accepted, not release-qualified.** Tests require execution on an exact candidate and control-preservation review.

Remaining required obligations of this work order: (1) make authenticated proof mandatory for the qualified installation/upgrade entry path without an unpinned bypass, (2) actually install distribution-owned members as exact verified ZIP bytes with manifest/ownership reconciliation, (3) test source-byte equality, stale authorizations, concurrent mutation, crash and recovery in Linux and Windows, and (4) preserve SF-06 conflict rejection, project-owned instructions and optional manual routing. Those items remain blockers for PR #24 completion and all downstream PRs.

Trust mode remains an externally authenticated digest pin, not verified publisher signatures or attested out-of-band channel. No target repo was modified; all changes remain in `spsoftwarefc/s-f` stacked development branch. No PR merge or deployment is authorized.
