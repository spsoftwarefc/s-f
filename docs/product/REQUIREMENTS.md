# Product requirements and acceptance trace

These are product obligations, not evidence that implementation has passed.

| Requirement | Contract | First package | Independent acceptance |
| --- | --- | --- | --- |
| SF-R01 | New/existing/monorepo/unknown stacks | SF-07 | Synthetic fixture matrix |
| SF-R02 | Project-owned commands and deployment | SF-04 | Custom command adapter negative/positive tests |
| SF-R03 | Preserve target authority/controls | SF-05 | Unrelated-instruction byte preservation test |
| SF-R04 | Dry-run, repeatable apply, upgrade/remove | SF-05/06 | Zero-write and interrupted-apply tests |
| SF-R05 | Pinned authenticated factory distribution | SF-13 | Tampered/unauthenticated bundle rejection |
| SF-R06 | End-to-end production lifecycle | SF-08/16 | Signal-to-release/outcome trace |
| SF-R07 | Verified rather than asserted evidence | SF-09/10 | Forged/stale/missing receipt tests |
| SF-R08 | No mandatory reviewer request/approval | SF-11 | Acceptance without reviewers |
| SF-R09 | Authorized development continues | SF-08/11 | Blocked external effect does not block independent work |
| SF-R10 | Budget and serial-default concurrency | SF-18 | Budget/cancellation/lease tests |
| SF-R11 | Install is not release qualification | SF-07 | Missing-tests fixture installs but fails readiness |
| SF-R12 | Accurate CI/host capability status | SF-10 | Unsupported controls reported missing/unknown |

Every requirement remains unqualified until its named acceptance test is executed and verified.

## SF-19 cumulative status — source integration vs product readiness

Status as of 8 October 2026: pending PR #28. SF-00–SF-13 are integrated through PR #22; PR #23–#27 development candidates passed their respective scoped PR-stage checks, but no cumulative PR #28 protected integration has yet occurred. A final merge or CI run does not retroactively authorize production operation.

| Requirement group | Source/development evidence | Independent product-release qualification |
| --- | --- | --- |
| SF-R01–SF-R04 | Historical fixture coverage and SF-13I pinned lifecycle candidate | Target-project installs/controls must be independently qualified per adopter |
| SF-R05 | Exact pinned archive and installed bytes on local fixtures | BLOCKED: authenticated publisher/signature and out-of-band trust custody |
| SF-R06 | SF-14–SF-16 source planning, fake dispatch and offline observation, integrated in SF-19 fixture | BLOCKED: real target, durable recovery, live observation and operational authorization |
| SF-R07–SF-R09 | Existing evidence/review gates and no mandatory reviewer request; pending protected cumulative checks | Provider policy, artifact and release authority must be independently bound |
| SF-R10 | No implementation claimed; SF-18 deferred | UNMET: production agent budget/concurrency qualification, if required by adopter |
| SF-R11–SF-R12 | Explicit all-false production release/authority flags and qualified-vs-unknown distinctions | BLOCKED unless external deployment/host controls are verified |

`developmentFixturePassed` or a protected GitHub merge **must not** be construed as `releaseQualified` or `deploymentAuthorized`.
