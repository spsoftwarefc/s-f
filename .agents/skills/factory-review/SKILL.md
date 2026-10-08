---
name: factory-review
description: Review an s-f candidate against its declared package, actual diff, executable evidence and preserved project controls.
---

Review the actual candidate revision and diff, not only the implementation summary.

Start with the active work order and verify:
- declaration preceded implementation;
- changed paths are inside scope or explicitly amended;
- every obligation has the required before/after or preservation evidence;
- expected results were independently defined rather than copied from implementation output;
- callers, failure paths, ownership boundaries and affected tests were reviewed;
- candidate changes did not weaken the tests, policy or checker used to accept themselves without an explicit control-change assessment;
- evidence is bound to the revision it claims to verify;
- skipped, cancelled, missing, stale or inaccessible required evidence is not labelled success.

Run targeted counterexamples only where a concrete unresolved risk remains. Prefer local verification for ordinary behavior and reserve hosted runs for provider-specific facts.

Return blockers first, with the affected file/symbol or contract and the exact acceptance condition. A substantive self-review is required; assigned reviewers, approving-review counts and external scoring services are not factory prerequisites.

Do not merge or deploy solely because review passes; those effects follow the active user/project authorization.
