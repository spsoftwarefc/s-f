# s-f — product vision and scope

s-f is a portable, repository-local software production system usable by human developers or coding agents. It supports planning, bounded implementation, deterministic validation, evidence-backed review, release preparation and operations without replacing project domain authority.

The initial product is an offline-first Python CLI and pinned vendored factory bundle. It supports new repositories, existing applications, monorepos and unknown stacks through explicit command adapters.

## Principles
- Existing project instructions, architecture, tests, CI and release permissions remain authoritative.
- A work order is declared before implementation; state is derived from evidence, not status prose.
- Discovery never executes repository commands.
- Installation is distinct from release qualification.
- A candidate does not validate its own weakening of safety controls.
- One package / one PR by default. Stack on the preceding branch and merge only at the user-specified boundary.
- Development testing is local-first; hosted CI is used only when provider-specific or integration evidence is necessary.
- No required reviewers, approving-review count, paid service or subjective score as a factory-internal acceptance gate.
- Merging, deploying and external actions require explicit authorization.

## Non-goals for first release
No required hosted orchestration, continuous autonomous agents, telemetry-triggered code execution, paid review service, cloud database, trading domain logic or blanket claims of universal stack understanding.

## Qualification
G0 source baseline; G1 contracts; G2 installation/portability; G3 representative package; G4 candidate acceptance; G5 release/recovery; G6 operation. Missing, skipped or inaccessible evidence does not satisfy required gates.
