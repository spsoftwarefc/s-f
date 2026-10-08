# Agent workflow index

Status: INFORMATIVE. Read `AGENTS.md` first. `PLAN.md` and the normative inventory retain contract authority.

Use only the skill needed for the current task; these are repository-local instructions, not installed third-party plugins.

| Task | Read |
| --- | --- |
| Implement a bounded contract or code change | [.agents/skills/bot-implementation/SKILL.md](.agents/skills/bot-implementation/SKILL.md) |
| Assess a pushed commit or milestone closure | [.agents/skills/bot-review/SKILL.md](.agents/skills/bot-review/SKILL.md) |
| Find dependencies, contracts, fixtures and mirrored implementations | [.agents/skills/bot-context/SKILL.md](.agents/skills/bot-context/SKILL.md) |

[Execution guide](docs/AGENT_EXECUTION_GUIDE.md) defines domain acceptance references, domain review rules and stage work packages.
[Research decision](docs/reviews/AGENT_TOOLING_RESEARCH.md) explains graph-tool selection and excluded skills.

Claude Code reads `CLAUDE.md`, which imports `AGENTS.md`; the latter routes here. Agents without automatic skill discovery must open the relevant file explicitly. Do not maintain duplicate skill bodies in multiple agent directories.

## Production Factory routing

For a new or continuing work package, read [Factory workflow](docs/factory/WORKFLOW.md) and [Bot Trader adapter](docs/factory/PROJECT.md), then use the applicable existing skill above. These documents wrap the existing implementation/review process; they are not additional installed skills.

[Work-order checklist](docs/factory/WORK_ORDER.md) is mandatory for every implementation work package:
- commit its work order before changing code;
- follow its structure, proof, evidence and handoff checkpoints.

Existing acceptance rows supply the obligations a work order references; they do not replace the work order. [Migration assessment](docs/factory/MIGRATION_REVIEW.md) records the source decisions and preservation mapping.
