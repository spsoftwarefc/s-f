# AGENTS.md — s-f

This repository builds the reusable s-f Software Factory. It grants no authority over target repositories, deployment destinations, credentials, or production systems unless a later project-specific adapter explicitly supplies that authority.

Read, in order:
1. `docs/factory/PROJECT.md`
2. `docs/factory/WORKFLOW.md`
3. `docs/factory/WORK_ORDER.md`
4. `SKILLS.md`
5. the active package under `docs/factory/work-orders/`

Before implementation, commit a bounded work order with its baseline revision, scope, obligations and proof expectations. Use one active package and one PR at a time unless the user has set an explicit stacked merge cadence.

During implementation:
- preserve unrelated work and existing project-owned controls;
- prefer local or ChatGPT-side checks during the edit loop;
- use GitHub Actions only when hosted/provider-specific evidence is required;
- do not rerun an unchanged candidate for presentation;
- record failed, skipped, unavailable and unknown checks honestly;
- do not request reviewers merely to satisfy the factory;
- do not merge or deploy until the active user instruction authorizes that effect.

Repository-local skills live only under `.agents/skills/`. Host adapters such as `CLAUDE.md` point here rather than copying the policy body.

The CTJ bot is extraction provenance only. Trading rules, exchange procedures, credentials, historical stage status and bot-specific acceptance logic are not s-f authority.
