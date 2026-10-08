---
name: factory-context
description: Build bounded repository context for an s-f work package without executing discovered project code.
---

Start from the exact repository revision, active work order and dirty paths. Read the repository's own instructions before inferring conventions.

Use `tools/context_map.py` when applicable to obtain a bounded advisory map, outline or whole-token reference search. Treat its output as discovery only, not as proof of semantic completeness.

Map the minimum useful relationships for the package:
requirement/decision -> owning document -> implementation -> callers/consumers -> tests/fixtures -> verification gate.

Rules:
- discovery is read-only;
- do not execute scripts merely because inventory finds them;
- do not assume a filename is authoritative without the project adapter;
- unresolved imports/references widen inspection only when relevant;
- record the candidate revision and any working-tree fingerprint used for discovery;
- keep secrets, generated datasets, dependency directories and unrelated large trees out of context;
- broaden the map only for a concrete unanswered dependency.

For unknown stacks, report uncertainty rather than inventing a parser or command.
