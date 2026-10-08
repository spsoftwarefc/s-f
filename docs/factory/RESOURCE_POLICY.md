# Repository resource policy

Status: active for s-f development.

The factory optimizes for evidence per unit of compute rather than maximum automation volume.

- Default to one active package and one PR at a time; stacked PRs are allowed when the user sets an explicit merge pile.
- Development verification runs locally or in the active coding environment first.
- GitHub Actions is used for provider-specific evidence or final integration evidence, not as the inner development loop.
- Avoid duplicate push + pull-request workflows unless they prove different identities.
- Do not rerun an unchanged candidate solely to obtain a newer green badge.
- Expensive or network-dependent suites must be explicit/on-demand until their value is demonstrated.
- Production hosts and credentials are not used as generic CI workers.
- Record unsupported or unavailable checks as unknown/missing, never pass.

SF-00 deliberately installs no GitHub Actions workflow.
