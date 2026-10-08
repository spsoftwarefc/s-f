# SF-R22 — Post-merge reconciliation evidence

**Stage:** factual source/CI reconciliation, no runtime changes; post-merge documentation PR #23 candidate. This document does not declare SF-13 release acceptance or product deployment authority.

## Source identity and observed protected integration

- Repo: `spsoftwarefc/s-f`; baseline `main` SHA `6c82b1230046650afcf28a61d7c8da7f8d157773`, tree `d95b8fc15c358992961e98d0adeb9f90dd07db09`.
- [PR #22](https://github.com/spsoftwarefc/s-f/pull/22): merged 2026-10-08 15:33:58 UTC (18:33:58 EAT); pre-queue source head `d9bded6dddcc98bf75b362c7a870fc87be4e9cb5`, base `9178dd0d6e0f0dee49d1b4f693bdf8d5f59ff2c5`.
- [Merge-group run #37801503467](https://github.com/spsoftwarefc/s-f/actions/runs/37801503467): event `merge_group`, attempt 1, head `6c82b1230046650afcf28a61d7c8da7f8d157773`, completed with conclusion `success`. Its GitHub `head_commit.tree_id` is `d95b8fc15c358992961e98d0adeb9f90dd07db09`.
- Individual jobs: Linux `113394612799` success, Windows `113394612438` success, `sf07-acceptance` `113395393182` success. These are merge-group, not just PR-stage, results. The historical PR-stage run belongs to a different synthetic candidate SHA.
- PRs #17–#21 closed without individual merges. SF-08–SF-13 source is now incorporated in `main`, but current readiness is *development preview*.

## Source-preservation and diff-review disposition

- README and PROJECT adapter previously described PR #22 as open/unmerged. Corrected statements cite observed GitHub PR/CI facts and distinguish package incorporation from acceptance; SF-13 historical dossier is append-only.
- No source runtime, workflow, test oracle, security gate, trust authority or external repository was changed in this package. No separate hosted run is requested for a factual documentation-only change.
- Full SF-13 acceptance is **outstanding**: installer does not consume/enforce lock, publisher signatures are not verified, and out-of-band trust-pin provisioning cannot be attested merely from matching checksums.
- Remaining mandatory work: corrective SF-13/SF-06 integration, SF-14 artifact and release planning, SF-15 deployment/recovery, SF-16 operations, SF-19 v1 qualification. SF-17 and SF-18 remain optional.
- This record binds the *baseline integration*, not the future PR #23 head; that head must be recorded separately if used for a CI/review claim.

## Negative and excluded claims

No new Windows/Linux test pass, full codebase assurance, installer safety proof, publisher identity, release deployment or independent security-scanner result is asserted by this reconciliation. Existing historical source-bound evidence is preserved.
