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
