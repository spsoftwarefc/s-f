---
name: bot-implementation
description: Implement and self-review changes in the standalone spot bot using its normative contracts, mirrored arithmetic and fixture evidence. Use for remediation or stage implementation; does not authorize live trading or holdout access.
---

Read `AGENTS.md`, then the relevant domain obligations in `docs/AGENT_EXECUTION_GUIDE.md`.
Resolve actual filenames through `docs/NORMATIVE_INVENTORY.json`; do not infer a rule from the latest filename or a completion report.

`docs/factory/WORK_ORDER.md` is the single authoritative checklist for checkpoints, fields, proof, evidence, completion stages and handoff. This skill says how to apply it to the bot and does not restate it.

For the requested scope:
1. If you are receiving or resuming work, run the WORK_ORDER.md §6 resume checkpoint first and act on its report. Otherwise establish full HEAD, branch, dirty paths and accepted decisions (WORKFLOW.md §3), build a bounded impact map using the bot-context skill, and for a new work order capture the expected project-map impact plus affected invariants/tests in `declaredImpact`. Record `context_map --find` and its fingerprint as advisory discovery, or the concrete reason it cannot run.
2. Write the domain acceptance rows required by the guide (§4) and carry each obligation into the work order with its independently derived expected result.
3. Reproduce the defect through the real event/input boundary before changing code, or record why a baseline cannot run. For temporal behavior, cause the first and subsequent events in one run; pre-seeded state alone is restart evidence, not evidence that the first event records state.
4. Complete WORK_ORDER.md §1 and the before-implementation column of §2, then commit the work order before any implementation.
5. Implement the slice following the representative modules' conventions, and inspect its callers, opposite branch, failure path and mirror. Run focused checks, correct findings locally, then run the applicable final verification once.
6. Update the authoring source, emitted fixtures, matrix, incident definitions and manifest when affected. A changed safety rule is a decision proposal, not a fixture correction. Preserve its original text and gate; never approve it through implementation.
7. Complete the before-handoff column of §2 and add the evidence record in a separate later commit (§4). For schemaVersion 2 work orders, use the schemaVersion 3 impact review: recheck every declared invariant/test, record unexpected impact and explicitly unaffected boundaries, and amend `declaredImpact` if the checker derives additional map impact. Check it at the acceptance stage (§5), and report pending decisions and counterexamples with it.

Continue authorized reversible work without asking after each file or test. Ask only for an external policy/permission decision that blocks the affected slice; keep independent work moving. Do not silently weaken a requirement to match a model limitation.
A failing semantic check is investigated, not bypassed through a looser oracle or a deferral.

Completion follows WORK_ORDER.md §5 and §7 together with the guide's domain completion conditions (§1). Test counts, hashes, a graph match and a green workflow are supporting evidence, not acceptance by themselves.
