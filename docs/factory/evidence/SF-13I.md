# SF-13I — Pinned installation and source byte mapping

Status: **implementation candidate, tests and full acceptance not yet independently qualified**.

Baseline: PR #23 branch head `95ffa63ac79857f72d56a21376e8c851bac33801`, tree `bf1cb51a1022fd5339a1244d9668f73b9e29cfe9`. Work order `docs/factory/work-orders/SF-13I.json` was committed first at `b2d44d356ed46ec35548ac501730635b4734a55d`, with an isolated, explained scope amendment before new installer/test files.

## Implemented candidate boundaries

- `src/sf/distribution.py`: strict canonical installation lock compared with an out-of-band pinned archive.
- `src/sf/pinned.py`: source-member exact bytes, generated target metadata, path ownership, immutable plan, journal and checked recovery.
- `src/sf/lifecycle.py` and `src/sf/cli.py`: qualified-path routing and mandatory CLI inputs; explicit unpinned preview compatibility.
- `tests/test_pinned.py` and regression updates: binary member equality, tampering, upgrade, preserve local edits, interrupted recovery, project-owned instructions and removal.

## Evidence and residual risk

No native platform test result, external distribution trust-authenticity claim, publisher signature, public release or deployment is claimed in this document. The retained Python-level legacy preview path is unqualified. Hostile concurrent writers and platform durability require further qualification. PR #24 remains stacked on #23, with only PR #28 permitted as the final mainline integration candidate.
