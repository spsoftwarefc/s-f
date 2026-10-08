---
name: bot-review
description: Review a standalone spot-bot commit against contracts, executable behavior and exact-commit evidence, including accounting, recovery and milestone gates. Use for developer completion reports and pre-merge assessment.
---

Read the affected acceptance rows in `docs/AGENT_EXECUTION_GUIDE.md` and the repository-local bot-context skill. Inspect the actual commit and diff, not only the author's summary.

Start from the package's work order and evidence record, using the fields defined in `docs/factory/WORK_ORDER.md`, the single authoritative checklist. Run `tools/check_factory_evidence.py --resume <work order>` and `--stage acceptance` at the reviewed revision. Then confirm each of the following:
- the work order was declared before implementation, and its expectations were kept or amended with reasons;
- each obligation's before state (reproducer, observation or recorded limitation) is paired with after evidence of the declared proof kind;
- the structure review answers WORK_ORDER.md §2: conventions followed and departures, migrated callers, no hidden authority in helpers, no duplication, hidden state or swallowed errors;
- every changed path, including commits after the evidence candidate, is covered by current evidence;
- for schemaVersion 2 work orders, the checker-derived project-map impact is covered by `declaredImpact`, every declared invariant names its exercising tests and is rechecked, and the record does not substitute authored actual-impact claims for the checker result.

A record that passes the checker is still reviewed for truth; the checker validates form and binding, not meaning.

Review each claimed correction with three questions:
- Is the underlying rule unchanged or is this a newly proposed policy?
- Does the implementation derive the outcome from raw evidence, or does the fixture supply the conclusion?
- Is the evidence exercising the whole required transition, or only a convenient pre-seeded state?

For arithmetic, examine parser, input domain, every operation and caller; test at altered Decimal context precision and compare independent expected values across languages.
For recovery, separate reservation from confirmed protection, current incidents from immutable audit records, adoption from dispatch authorization, and eligibility gap from absolute order quantity.
For incidents, inspect trigger, scope, clear predicate, authority and resume behavior together.
For grouping, enumerate every contract precondition and where its evidence is checked; a helper with fewer inputs needs a proven upstream gate and an integration test.

Run a targeted counterexample when a concrete risk remains. Label findings as reproduced, source-confirmed, policy decision, or unverified. Do not label an unrun scenario as a reproduced defect.
Read CI head SHA and logs; push-triggered runs may be absent from PR-only APIs. Do not rerun an unchanged suite merely to repeat a verified result.

Return blockers first with file/symbol, impact and exact acceptance test. Separate milestone acceptance, contract freeze, venue qualification, production implementation and live authorization.
Stop expanding the review once affected obligations are resolved and required gates pass. Do not add speculative infrastructure or demand independent human reviewers for a private solo project.
