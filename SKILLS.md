# s-f skill routing

Status: active repository-local routing.

Use only the skill needed for the current task. The canonical bodies are under `.agents/skills/`; do not duplicate them into host-specific directories.

| Task | Skill |
| --- | --- |
| Discover affected files, references and bounded dependency context | [.agents/skills/factory-context/SKILL.md](.agents/skills/factory-context/SKILL.md) |
| Implement a declared work package | [.agents/skills/factory-implementation/SKILL.md](.agents/skills/factory-implementation/SKILL.md) |
| Review a candidate against its work order and evidence | [.agents/skills/factory-review/SKILL.md](.agents/skills/factory-review/SKILL.md) |

The reusable lifecycle is `docs/factory/WORKFLOW.md`; package checkpoints are `docs/factory/WORK_ORDER.md`; repository-specific boundaries are `docs/factory/PROJECT.md`.

No skill grants merge, deployment, credential, external-service or target-repository authority. Those remain explicit effects controlled by the active project/user instruction.
