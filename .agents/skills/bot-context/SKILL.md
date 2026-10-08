---
name: bot-context
description: Map a spot-bot change to its source dependencies, normative rules, fixtures and mirrored implementations before editing. Use when locating impact or reviewing a cross-file change.
---

Start with full commit and dirty paths. Read `docs/NORMATIVE_INVENTORY.json` and the relevant rows of `docs/REQUIREMENT_TRACEABILITY_v1.2.0.md`.
Run `python tools/context_map.py --paths <changed-path> --depth 1` for a bounded candidate map. Multiple paths are accepted.
The map uses local import extraction and literal references; it is NOT a complete call graph, semantic verifier or proof that no other files are affected. Follow its unresolved imports and inspect actual symbols with `rg`.

Map-first reading keeps context for the lines that matter:
1. `python tools/context_map.py --outline <file>...` lists Python and TypeScript symbols, Markdown sections and top-level JSON keys, each with its line span.
2. `python tools/context_map.py --find <name>...` lists definitions and every whole-token reference, grouped by the enclosing symbol or section, across code, contracts and fixtures.
3. Read only the returned span with a line offset and limit. Widen to neighbouring spans when the span is insufficient; read a whole file only when you need its overall structure or it is short.

Outlines narrow where to read; they do not replace reading the code you change, its callers, its mirror, its fixture and its contract row. Spans come from a lexical scan: if one looks cut short, read further before acting. Add `--format json` when a tool consumes the output.
Read the implementation, its callers, the Python/TypeScript mirror, fixture authoring module, emitted expected outcome, contract and incident row. Generated fixtures are not the primary editing surface.

Map these relations explicitly:
requirement -> contract -> producer -> consumer -> mirror -> fixture -> runner -> CI gate.
Code graphs miss contract-policy relationships and dynamic dispatch; the evidence matrix supplies those edges.
Record source commit plus working-tree fingerprint. Rebuild after edits; never use a stale map as exclusion evidence.

Default: local, no network, no model calls, no credentials. Graph output goes to scratch/stdout and is regenerable.
Graft and CodeGraph are not installed; map-first reading uses this repository's own tool. See `docs/reviews/AGENT_TOOLING_RESEARCH.md` before introducing any third-party graph tool.
Retrieve only one hop initially; broaden only for a specific unanswered dependency. Do not dump an entire repository graph into context.
